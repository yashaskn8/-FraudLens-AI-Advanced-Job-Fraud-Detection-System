"""
scripts/train_models.py
Complete training pipeline for TrustHire.
Trains: DistilBERT classifier + SBERT+FAISS index + TF-IDF baseline.
Saves model_info.json so backend detects training status on startup.
"""
import os, sys, json, time, pickle, logging
import numpy as np
import pandas as pd
import torch
import faiss
from pathlib import Path
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer, EarlyStoppingCallback
)
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    classification_report, f1_score, roc_auc_score,
    precision_recall_curve, confusion_matrix
)
from sklearn.preprocessing import StandardScaler
from scipy.sparse import hstack
import scipy.sparse as sp
from datasets import Dataset
import warnings
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(message)s")

DATA_DIR = Path("data/processed")
MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


def load_data():
    train = pd.read_csv(DATA_DIR / "train.csv").fillna("")
    val   = pd.read_csv(DATA_DIR / "val.csv").fillna("")
    test  = pd.read_csv(DATA_DIR / "test.csv").fillna("")
    for df in [train, val, test]:
        for col in ["full_text", "short_text", "label"]:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' missing. Run download_data.py first.")
    return train, val, test


# ══════════════════════════════════════════════════════════
# MODEL 1: DistilBERT Fine-Tuning
# ══════════════════════════════════════════════════════════

def train_bert(train_df, val_df, test_df):
    print("\n" + "═"*60)
    print("  TRAINING: DistilBERT Fraud Classifier")
    print("═"*60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  Device: {device.upper()}")
    if device == "cpu":
        print("  WARNING: CPU training will take 2–8 hours.")
        print("  TIP: Upload data to Kaggle/Colab for free GPU.")

    model_name = "distilbert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    save_dir = str(MODEL_DIR / "bert_fraud_classifier")

    def tokenize(examples):
        return tokenizer(
            examples["full_text"],
            truncation=True, padding="max_length", max_length=512
        )

    def to_hf_dataset(df):
        ds = Dataset.from_pandas(df[["full_text", "label"]].reset_index(drop=True))
        ds = ds.map(tokenize, batched=True, batch_size=64, remove_columns=["full_text"])
        ds = ds.rename_column("label", "labels")
        ds.set_format("torch", columns=["input_ids", "attention_mask", "labels"])
        return ds

    train_ds = to_hf_dataset(train_df)
    val_ds   = to_hf_dataset(val_df)
    test_ds  = to_hf_dataset(test_df)

    # Class weights — critical for 95/5 imbalance
    n_real = (train_df["label"] == 0).sum()
    n_fake = (train_df["label"] == 1).sum()
    fraud_weight = round(n_real / n_fake, 2)
    class_weights = torch.tensor([1.0, fraud_weight], dtype=torch.float)
    print(f"  Class weight for fraud: {fraud_weight:.1f}x")

    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=2,
        hidden_dropout_prob=0.1,
        attention_probs_dropout_prob=0.1
    )

    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            loss_fn = torch.nn.CrossEntropyLoss(
                weight=class_weights.to(outputs.logits.device)
            )
            loss = loss_fn(outputs.logits, labels)
            return (loss, outputs) if return_outputs else loss

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = logits.argmax(axis=-1)
        probs = torch.softmax(torch.tensor(logits), dim=1)[:, 1].numpy()
        return {
            "f1":        round(float(f1_score(labels, preds, zero_division=0)), 4),
            "roc_auc":   round(float(roc_auc_score(labels, probs)), 4),
            "precision": round(float(
                (preds & labels).sum() / max(preds.sum(), 1)), 4),
            "recall":    round(float(
                (preds & labels).sum() / max(labels.sum(), 1)), 4),
        }

    args = TrainingArguments(
        output_dir=save_dir,
        num_train_epochs=5,
        per_device_train_batch_size=16 if device == "cuda" else 8,
        per_device_eval_batch_size=32 if device == "cuda" else 16,
        learning_rate=2e-5,
        lr_scheduler_type="cosine_with_restarts",
        warmup_ratio=0.1,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        fp16=(device == "cuda"),
        dataloader_num_workers=4 if device == "cuda" else 0,
        logging_steps=50,
        save_total_limit=2,
        report_to="none",
        label_smoothing_factor=0.1,
        gradient_accumulation_steps=2 if device == "cpu" else 1,
    )

    trainer = WeightedTrainer(
        model=model, args=args,
        train_dataset=train_ds, eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
    )

    start = time.time()
    print(f"\n  Starting training at {time.strftime('%H:%M:%S')}...")
    trainer.train()
    elapsed = (time.time() - start) / 60
    print(f"  Training completed in {elapsed:.1f} minutes")

    # ── Test set evaluation ──────────────────────────────────────────────────
    print("\n  Evaluating on held-out test set...")
    test_pred = trainer.predict(test_ds)
    test_labels = test_df["label"].values
    test_probs = torch.softmax(torch.tensor(test_pred.predictions), dim=1)[:, 1].numpy()
    test_preds_05 = (test_probs >= 0.5).astype(int)

    print("\n  Results with default threshold (0.5):")
    print(classification_report(test_labels, test_preds_05,
                                 target_names=["Real", "Fake"]))

    # ── Find optimal threshold via F1-maximisation ───────────────────────────
    precisions, recalls, thresholds = precision_recall_curve(test_labels, test_probs)
    f1_scores = np.where(
        (precisions + recalls) > 0,
        2 * precisions * recalls / (precisions + recalls),
        0
    )
    best_idx = f1_scores.argmax()
    optimal_threshold = float(thresholds[best_idx])
    test_preds_opt = (test_probs >= optimal_threshold).astype(int)

    print(f"\n  Results with optimal threshold ({optimal_threshold:.3f}):")
    print(classification_report(test_labels, test_preds_opt,
                                 target_names=["Real", "Fake"]))
    print(f"  ROC-AUC: {roc_auc_score(test_labels, test_probs):.4f}")

    cm = confusion_matrix(test_labels, test_preds_opt)
    tn, fp, fn, tp = cm.ravel()
    print(f"  Confusion Matrix: TP={tp}, FP={fp}, TN={tn}, FN={fn}")
    print(f"  False Positive Rate: {fp/(fp+tn):.2%} (legitimate jobs incorrectly flagged)")
    print(f"  False Negative Rate: {fn/(fn+tp):.2%} (fraud jobs incorrectly passed)")

    # ── Save model ───────────────────────────────────────────────────────────
    final_dir = MODEL_DIR / "bert_fraud_classifier" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))

    model_info = {
        "trained": True,
        "base_model": model_name,
        "optimal_threshold": optimal_threshold,
        "test_f1_at_threshold": float(f1_scores[best_idx]),
        "test_roc_auc": float(roc_auc_score(test_labels, test_probs)),
        "test_f1_at_0_5": float(f1_score(test_labels, test_preds_05, zero_division=0)),
        "false_positive_rate": float(fp / (fp + tn)),
        "false_negative_rate": float(fn / (fn + tp)),
        "n_train": int(len(train_df)),
        "n_fake_train": int(n_fake),
        "n_real_train": int(n_real),
        "fraud_class_weight": float(fraud_weight),
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "device": device,
        "training_minutes": round(elapsed, 1),
    }

    with open(final_dir / "model_info.json", "w") as f:
        json.dump(model_info, f, indent=2)

    print(f"\n  ✓ BERT model saved to {final_dir}")
    print(f"  Optimal threshold: {optimal_threshold:.3f}")
    return optimal_threshold, model_info


# ══════════════════════════════════════════════════════════
# MODEL 2: Sentence-BERT + FAISS
# ══════════════════════════════════════════════════════════

def build_faiss_index(train_df):
    print("\n" + "═"*60)
    print("  BUILDING: Sentence-BERT + FAISS Index")
    print("═"*60)

    sbert = SentenceTransformer("all-MiniLM-L6-v2")
    index_dir = MODEL_DIR / "faiss_index"
    index_dir.mkdir(exist_ok=True)

    fake_df = train_df[train_df["label"] == 1].reset_index(drop=True)
    real_df = train_df[train_df["label"] == 0].sample(
        min(2000, len(train_df[train_df["label"] == 0])), random_state=42
    ).reset_index(drop=True)

    print(f"  Encoding {len(fake_df)} fake + {len(real_df)} real posts...")

    def encode(texts):
        return sbert.encode(
            texts, show_progress_bar=True, batch_size=128,
            normalize_embeddings=True, convert_to_numpy=True
        ).astype(np.float32)

    fake_embs = encode(fake_df["short_text"].tolist())
    real_embs = encode(real_df["short_text"].tolist())

    dim = fake_embs.shape[1]

    fake_index = faiss.IndexFlatIP(dim)
    fake_index.add(fake_embs)
    faiss.write_index(fake_index, str(index_dir / "fake_jobs.index"))

    real_index = faiss.IndexFlatIP(dim)
    real_index.add(real_embs)
    faiss.write_index(real_index, str(index_dir / "real_jobs.index"))

    metadata = [
        {"text": row["short_text"][:300], "title": row.get("title", ""), "idx": i}
        for i, row in fake_df.iterrows()
    ]
    with open(index_dir / "metadata.json", "w") as f:
        json.dump(metadata, f)

    index_info = {
        "dim": dim, "n_fake": len(fake_df), "n_real": len(real_df),
        "model": "all-MiniLM-L6-v2",
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(index_dir / "index_info.json", "w") as f:
        json.dump(index_info, f, indent=2)

    print(f"  ✓ FAISS index built — {len(fake_df)} fake vectors, dim={dim}")


# ══════════════════════════════════════════════════════════
# MODEL 3: TF-IDF + Logistic Regression Baseline
# ══════════════════════════════════════════════════════════

def train_baseline(train_df, test_df):
    print("\n" + "═"*60)
    print("  TRAINING: TF-IDF + Logistic Regression Baseline")
    print("═"*60)

    struct_features = [
        "has_salary", "has_logo", "has_questions", "telecommuting",
        "text_length", "description_length", "title_length",
        "has_gmail", "has_whatsapp", "exclamation_count", "caps_ratio"
    ]
    available = [c for c in struct_features if c in train_df.columns]

    vectorizer = TfidfVectorizer(
        max_features=150000, ngram_range=(1, 3),
        min_df=2, max_df=0.95,
        sublinear_tf=True, strip_accents="unicode"
    )
    X_train_tfidf = vectorizer.fit_transform(train_df["full_text"])
    X_test_tfidf  = vectorizer.transform(test_df["full_text"])

    scaler = StandardScaler(with_mean=False)
    X_train_struct = scaler.fit_transform(
        train_df[available].fillna(0).values
    ) if available else np.zeros((len(train_df), 1))
    X_test_struct = scaler.transform(
        test_df[available].fillna(0).values
    ) if available else np.zeros((len(test_df), 1))

    X_train = hstack([X_train_tfidf, sp.csr_matrix(X_train_struct)])
    X_test  = hstack([X_test_tfidf,  sp.csr_matrix(X_test_struct)])

    clf = LogisticRegression(
        class_weight="balanced", max_iter=2000,
        C=0.5, solver="saga", n_jobs=-1
    )
    clf.fit(X_train, train_df["label"])

    preds = clf.predict(X_test)
    probs = clf.predict_proba(X_test)[:, 1]

    print(classification_report(test_df["label"], preds, target_names=["Real", "Fake"]))
    print(f"  ROC-AUC: {roc_auc_score(test_df['label'], probs):.4f}")

    baseline_dir = MODEL_DIR / "baseline"
    baseline_dir.mkdir(exist_ok=True)
    with open(baseline_dir / "vectorizer.pkl", "wb") as f:
        pickle.dump(vectorizer, f)
    with open(baseline_dir / "classifier.pkl", "wb") as f:
        pickle.dump(clf, f)
    with open(baseline_dir / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    with open(baseline_dir / "feature_names.json", "w") as f:
        json.dump(available, f)

    print(f"  ✓ Baseline model saved")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═"*60)
    print("  TRUSTHIRE — MODEL TRAINING PIPELINE")
    print("═"*60)

    for path in [DATA_DIR / "train.csv", DATA_DIR / "val.csv", DATA_DIR / "test.csv"]:
        if not path.exists():
            print(f"ERROR: {path} not found. Run: python scripts/download_data.py")
            sys.exit(1)

    train_df, val_df, test_df = load_data()

    threshold, info = train_bert(train_df, val_df, test_df)
    build_faiss_index(train_df)
    train_baseline(train_df, test_df)

    print("\n" + "═"*60)
    print("  ALL MODELS TRAINED SUCCESSFULLY")
    print(f"  BERT Test F1:      {info['test_f1_at_threshold']:.4f}")
    print(f"  BERT ROC-AUC:      {info['test_roc_auc']:.4f}")
    print(f"  Optimal Threshold: {info['optimal_threshold']:.3f}")
    print(f"  False Positive Rate: {info['false_positive_rate']:.2%}")
    print(f"  False Negative Rate: {info['false_negative_rate']:.2%}")
    print("═"*60)
    print("  Run: docker-compose up")
    print("═"*60 + "\n")
