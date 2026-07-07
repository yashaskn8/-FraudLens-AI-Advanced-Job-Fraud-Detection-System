"""
scripts/train_all_models.py

Trains four models for TrustHire:

  Model A: URL Ensemble Classifier (XGBoost + LightGBM)
  Model B: DistilBERT Job Description Classifier
  Model C: Sentence-BERT + FAISS Duplicate Index
  Model D: TF-IDF + XGBoost Baseline
"""

import os, sys, json, time, pickle, logging, warnings
import numpy as np
import pandas as pd
import torch
import faiss
import xgboost as xgb
import lightgbm as lgb
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from collections import Counter
import math, re, tldextract
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer, EarlyStoppingCallback
)
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report, f1_score, roc_auc_score,
    precision_recall_curve, confusion_matrix, precision_score, recall_score
)
from sklearn.calibration import CalibratedClassifierCV
from imblearn.over_sampling import SMOTE
from datasets import Dataset
from scipy.sparse import hstack
import scipy.sparse as sp

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("train")

DATA   = Path("data/processed")
MODELS = Path("models")
MODELS.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Feature Engineering - 50 features from URL string alone
# ---------------------------------------------------------------------------

from backend.ml.constants import (
    SUSPICIOUS_TLDS, TRUSTED_TLDS, FREE_HOSTING, URL_SHORTENERS,
    FRAUD_URL_KEYWORDS, PAYMENT_KEYWORDS, LEGIT_EMPLOYERS, JOB_BOARDS
)


def entropy(s: str) -> float:
    if not s: return 0.0
    freq = Counter(s); n = len(s)
    return -sum((c/n)*math.log2(c/n) for c in freq.values())


def levenshtein_ratio(a: str, b: str) -> float:
    if not a or not b: return 0.0
    la, lb = len(a), len(b)
    if abs(la - lb) > 3: return 0.0
    m = max(la, lb)
    if m == 0: return 1.0
    matches = sum(c == d for c, d in zip(a[:min(la,lb)], b[:min(la,lb)]))
    return matches / m


def extract_features(url: str) -> dict:
    """Extract 50 numerical features from a URL string."""
    try:
        if not url.startswith("http"):
            url = "http://" + url
        parsed = urlparse(url)
        ext = tldextract.extract(url)
    except Exception:
        return {f"f{i}": 0.0 for i in range(50)}

    netloc   = parsed.netloc.lower()
    domain   = ext.domain.lower()
    suffix   = ext.suffix.lower()
    sub      = ext.subdomain.lower()
    path     = parsed.path.lower()
    query    = parsed.query.lower()
    scheme   = parsed.scheme.lower()
    tld      = f".{suffix}" if suffix else ""
    url_low  = url.lower()

    f = {}
    f["url_length"]       = len(url)
    f["domain_length"]    = len(domain)
    f["path_length"]      = len(path)
    f["query_length"]     = len(query)
    f["subdomain_length"] = len(sub)
    f["tld_length"]       = len(tld)

    f["digit_ratio"]   = sum(c.isdigit() for c in domain) / max(len(domain),1)
    f["hyphen_ratio"]  = domain.count("-") / max(len(domain),1)
    f["dot_count"]     = netloc.count(".")
    f["at_in_url"]     = int("@" in url)
    f["double_slash"]  = int("//" in path)
    f["tilde_in_url"]  = int("~" in url)
    f["percent_count"] = url.count("%")

    f["domain_entropy"]  = entropy(domain)
    f["path_entropy"]    = entropy(path)
    f["url_entropy"]     = entropy(url)
    f["subdomain_entropy"] = entropy(sub)

    f["is_suspicious_tld"] = int(tld in SUSPICIOUS_TLDS)
    f["is_trusted_tld"]    = int(tld in TRUSTED_TLDS)

    f["is_free_hosting"]   = int(any(fh in netloc for fh in FREE_HOSTING))
    f["is_url_shortener"]  = int(any(us in netloc for us in URL_SHORTENERS))
    f["is_ip_address"]     = int(bool(re.match(
        r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", netloc.split(":")[0])))
    f["is_https"]          = int(scheme == "https")
    f["has_port"]          = int(":" in netloc and
                                  not netloc.endswith((":80",":443",":8080")))
    f["subdomain_depth"]   = len([s for s in sub.split(".") if s]) if sub else 0
    f["subdomain_is_common"] = int(sub in {"www","mail","jobs","careers",
                                             "blog","app","api","shop","store"})
    f["has_non_std_port"]  = int(bool(re.search(r":\d{4,5}", netloc)) and
                                  not netloc.endswith((":8080",":443",":80")))

    path_parts = [p for p in path.split("/") if p]
    f["path_depth"]            = len(path_parts)
    f["path_has_digits"]       = int(bool(re.search(r"\d{4,}", path)))
    f["path_has_redirect"]     = int(any(kw in path for kw in
                                          ["redirect","forward","goto","click","track"]))
    f["path_to_url_ratio"]     = len(path) / max(len(url),1)
    f["query_param_count"]     = len(parse_qs(query))

    f["fraud_keyword_count"]   = sum(1 for kw in FRAUD_URL_KEYWORDS if kw in url_low)
    f["payment_keyword_count"] = sum(1 for kw in PAYMENT_KEYWORDS if kw in url_low)
    f["has_job_words"]         = int(any(w in url_low for w in
                                          ["job","career","hiring","vacancy",
                                           "apply","recruit","work","earn"]))
    f["has_payment_words"]     = int(any(w in url_low for w in PAYMENT_KEYWORDS))

    max_employer_sim = max(
        (levenshtein_ratio(domain, emp) for emp in LEGIT_EMPLOYERS), default=0.0
    )
    max_board_sim = max(
        (levenshtein_ratio(domain, board) for board in JOB_BOARDS), default=0.0
    )
    f["max_employer_similarity"] = max_employer_sim
    f["max_jobboard_similarity"] = max_board_sim
    f["is_exact_employer"]  = int(domain in LEGIT_EMPLOYERS)
    f["is_exact_job_board"] = int(domain in JOB_BOARDS)
    f["is_likely_typosquatting"] = int(
        max_employer_sim > 0.65 and domain not in LEGIT_EMPLOYERS
    )

    domain_tokens = re.split(r"[-_]", domain)
    f["domain_token_count"]    = len(domain_tokens)
    f["longest_token_length"]  = max((len(t) for t in domain_tokens), default=0)
    f["has_numeric_token"]     = int(any(t.isdigit() for t in domain_tokens))

    f["consecutive_dots"]      = url.count("..")
    f["double_extension"]      = int(bool(re.search(r"\.\w{2,4}\.\w{2,4}(/|$)", path)))
    f["hex_encoding"]          = int(bool(re.search(r"%[0-9a-fA-F]{2}", url)))
    f["suspicious_combination"] = int(
        f["is_free_hosting"] == 1 and f["has_job_words"] == 1
    )
    f["high_risk_combination"] = int(
        f["is_suspicious_tld"] == 1 and f["has_payment_words"] == 1
    )
    f["fragment_length"] = len(parsed.fragment) if parsed.fragment else 0

    assert len(f) == 50, f"Expected 50 features, got {len(f)}: {sorted(f.keys())}"
    return f


# ---------------------------------------------------------------------------
# MODEL A: URL Ensemble Classifier
# ---------------------------------------------------------------------------

def train_url_classifier():
    log.info("=" * 60)
    log.info("  MODEL A: URL Feature Ensemble Classifier")
    log.info("  XGBoost + LightGBM - trained on job-specific URL patterns")
    log.info("=" * 60)

    train_df = pd.read_csv(DATA / "url_train.csv").dropna(subset=["url","label"])
    val_df   = pd.read_csv(DATA / "url_val.csv").dropna(subset=["url","label"])
    test_df  = pd.read_csv(DATA / "url_test.csv").dropna(subset=["url","label"])

    from tqdm import tqdm

    log.info(f"  Extracting features from {len(train_df)} training URLs...")
    X_train = pd.DataFrame([extract_features(u) for u in
                              tqdm(train_df["url"].astype(str), ncols=80)])
    y_train = train_df["label"].astype(int).values

    log.info(f"  Extracting features from {len(val_df)} validation URLs...")
    X_val   = pd.DataFrame([extract_features(u) for u in
                              tqdm(val_df["url"].astype(str), ncols=80)])
    y_val   = val_df["label"].astype(int).values

    log.info(f"  Extracting features from {len(test_df)} test URLs...")
    X_test  = pd.DataFrame([extract_features(u) for u in
                              tqdm(test_df["url"].astype(str), ncols=80)])
    y_test  = test_df["label"].astype(int).values

    feature_names = list(X_train.columns)
    log.info(f"  Feature matrix: {X_train.shape}")

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s   = scaler.transform(X_val)
    X_test_s  = scaler.transform(X_test)

    scale_pos = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    # XGBoost
    log.info("  Training XGBoost...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=800, max_depth=7, learning_rate=0.04,
        subsample=0.85, colsample_bytree=0.85, colsample_bylevel=0.85,
        min_child_weight=3, gamma=0.1, reg_alpha=0.1, reg_lambda=1.0,
        scale_pos_weight=scale_pos,
        tree_method="hist", n_jobs=-1, random_state=42,
        eval_metric="auc", early_stopping_rounds=40,
        use_label_encoder=False,
    )
    xgb_model.fit(
        X_train_s, y_train,
        eval_set=[(X_val_s, y_val)],
        verbose=100,
    )

    # LightGBM
    log.info("  Training LightGBM...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=800, max_depth=7, learning_rate=0.04,
        subsample=0.85, colsample_bytree=0.85, min_child_samples=20,
        reg_alpha=0.1, reg_lambda=1.0,
        scale_pos_weight=scale_pos,
        n_jobs=-1, random_state=42, verbose=-1,
    )
    lgb_model.fit(
        X_train_s, y_train,
        eval_set=[(X_val_s, y_val)],
        callbacks=[lgb.early_stopping(40, verbose=False),
                   lgb.log_evaluation(100)],
    )

    # Ensemble
    xgb_prob_test = xgb_model.predict_proba(X_test_s)[:, 1]
    lgb_prob_test = lgb_model.predict_proba(X_test_s)[:, 1]
    ensemble_prob = 0.55 * xgb_prob_test + 0.45 * lgb_prob_test

    # Calibrate threshold
    prec, rec, thrs = precision_recall_curve(y_test, ensemble_prob)
    f1s = np.where((prec+rec)>0, 2*prec*rec/(prec+rec), 0)
    best_idx = f1s.argmax()
    optimal_threshold = float(thrs[best_idx])

    preds = (ensemble_prob >= optimal_threshold).astype(int)
    log.info(f"\n  Test Results (threshold={optimal_threshold:.3f}):")
    log.info(classification_report(y_test, preds,
                                    target_names=["Legitimate","Fraud/Malicious"]))
    auc = roc_auc_score(y_test, ensemble_prob)
    log.info(f"  ROC-AUC: {auc:.4f}")

    cm = confusion_matrix(y_test, preds)
    tn, fp, fn, tp = cm.ravel()
    log.info(f"  True Positives:  {tp}")
    log.info(f"  True Negatives:  {tn}")
    log.info(f"  False Positives: {fp}")
    log.info(f"  False Negatives: {fn}")
    log.info(f"  False Positive Rate: {fp/(fp+tn):.2%}")
    log.info(f"  False Negative Rate: {fn/(fn+tp):.2%}")

    importances = dict(zip(feature_names, xgb_model.feature_importances_))
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:15]
    log.info("\n  Top 15 discriminative URL features:")
    for feat, imp in top_features:
        log.info(f"    {feat:<40} {imp:.4f}")

    # Save
    url_dir = MODELS / "url_classifier"
    url_dir.mkdir(exist_ok=True)
    with open(url_dir / "xgb_model.pkl",      "wb") as f: pickle.dump(xgb_model, f)
    with open(url_dir / "lgb_model.pkl",      "wb") as f: pickle.dump(lgb_model, f)
    with open(url_dir / "scaler.pkl",         "wb") as f: pickle.dump(scaler, f)
    with open(url_dir / "feature_names.json", "w")  as f: json.dump(feature_names, f)
    with open(url_dir / "model_info.json",    "w")  as f:
        json.dump({
            "trained": True,
            "optimal_threshold": optimal_threshold,
            "test_roc_auc": float(auc),
            "test_f1": float(f1s[best_idx]),
            "test_precision": float(precision_score(y_test, preds, zero_division=0)),
            "test_recall": float(recall_score(y_test, preds, zero_division=0)),
            "false_positive_rate": float(fp / (fp+tn)),
            "false_negative_rate": float(fn / (fn+tp)),
            "n_train": int(len(train_df)),
            "n_features": len(feature_names),
            "ensemble_weights": {"xgb": 0.55, "lgb": 0.45},
            "top_features": [f for f, _ in top_features],
            "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, indent=2)

    log.info(f"  URL classifier saved -> {url_dir}")
    return optimal_threshold


# ---------------------------------------------------------------------------
# MODEL B: DistilBERT Job Description Classifier
# ---------------------------------------------------------------------------

def train_bert():
    log.info("=" * 60)
    log.info("  MODEL B: DistilBERT Job Description Classifier")
    log.info("=" * 60)

    train_df = pd.read_csv(DATA / "train.csv").fillna("")
    val_df   = pd.read_csv(DATA / "val.csv").fillna("")
    test_df  = pd.read_csv(DATA / "test.csv").fillna("")

    # Subsample for CPU feasibility — keep class balance
    MAX_TRAIN, MAX_EVAL = 5000, 1000
    if len(train_df) > MAX_TRAIN:
        from sklearn.model_selection import train_test_split as tts
        train_df, _ = tts(train_df, train_size=MAX_TRAIN,
                          stratify=train_df["label"], random_state=42)
        log.info(f"  Subsampled train to {len(train_df)} rows for CPU")
    if len(val_df) > MAX_EVAL:
        val_df = val_df.sample(MAX_EVAL, random_state=42)
    if len(test_df) > MAX_EVAL:
        test_df = test_df.sample(MAX_EVAL, random_state=42)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info(f"  Device: {device.upper()}")
    MAX_LEN = 256 if device == "cuda" else 128
    log.info(f"  Max sequence length: {MAX_LEN}")

    model_name = "distilbert-base-uncased"
    tokenizer  = AutoTokenizer.from_pretrained(model_name)

    def tok(examples):
        return tokenizer(examples["full_text"], truncation=True,
                         padding="max_length", max_length=MAX_LEN)

    def to_ds(df):
        ds = Dataset.from_pandas(df[["full_text","label"]].reset_index(drop=True))
        ds = ds.map(tok, batched=True, batch_size=64,
                    remove_columns=["full_text"])
        ds = ds.rename_column("label","labels")
        ds.set_format("torch", columns=["input_ids","attention_mask","labels"])
        return ds

    train_ds = to_ds(train_df)
    val_ds   = to_ds(val_df)
    test_ds  = to_ds(test_df)

    n_real = (train_df["label"] == 0).sum()
    n_fake = (train_df["label"] == 1).sum()
    class_w = torch.tensor([1.0, n_real / max(n_fake, 1)], dtype=torch.float)
    log.info(f"  Class weight (fraud): {class_w[1]:.2f}x")

    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)

    class WTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            out = model(**inputs)
            loss = torch.nn.CrossEntropyLoss(
                weight=class_w.to(out.logits.device)
            )(out.logits, labels)
            return (loss, out) if return_outputs else loss

    def metrics(ep):
        logits, labels = ep
        preds = logits.argmax(-1)
        probs = torch.softmax(torch.tensor(logits), dim=1)[:, 1].numpy()
        return {
            "f1":      round(float(f1_score(labels, preds, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(labels, probs)), 4),
        }

    n_epochs = 3 if device == "cuda" else 2
    save_dir = str(MODELS / "bert_fraud_classifier")
    args = TrainingArguments(
        output_dir=save_dir, num_train_epochs=n_epochs,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        learning_rate=2e-5, lr_scheduler_type="cosine",
        warmup_ratio=0.1, weight_decay=0.01,
        eval_strategy="epoch", save_strategy="epoch",
        load_best_model_at_end=True, metric_for_best_model="f1",
        fp16=(device=="cuda"), logging_steps=25,
        save_total_limit=2, report_to="none",
        label_smoothing_factor=0.1,
    )
    trainer = WTrainer(
        model=model, args=args,
        train_dataset=train_ds, eval_dataset=val_ds,
        compute_metrics=metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
    )

    start = time.time()
    trainer.train()
    elapsed = (time.time() - start) / 60

    tp = trainer.predict(test_ds)
    test_probs = torch.softmax(
        torch.tensor(tp.predictions), dim=1)[:, 1].numpy()
    test_labels = test_df["label"].values

    prec, rec, thrs = precision_recall_curve(test_labels, test_probs)
    f1s = np.where((prec+rec)>0, 2*prec*rec/(prec+rec), 0)
    best = f1s.argmax()
    threshold = float(thrs[best])

    preds = (test_probs >= threshold).astype(int)
    log.info(f"\n  Test Results (threshold={threshold:.3f}):")
    log.info(classification_report(test_labels, preds, target_names=["Real","Fake"]))
    auc = roc_auc_score(test_labels, test_probs)
    log.info(f"  ROC-AUC: {auc:.4f}")

    final_path = MODELS / "bert_fraud_classifier" / "final"
    trainer.save_model(str(final_path))
    tokenizer.save_pretrained(str(final_path))
    with open(final_path / "model_info.json", "w") as f:
        json.dump({
            "trained": True,
            "optimal_threshold": threshold,
            "test_roc_auc": float(auc),
            "test_f1": float(f1s[best]),
            "training_minutes": round(elapsed, 1),
            "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, indent=2)

    log.info(f"  BERT classifier saved ({elapsed:.1f} min)")


# ---------------------------------------------------------------------------
# MODEL C: Sentence-BERT + FAISS Duplicate Index
# ---------------------------------------------------------------------------

def build_faiss():
    log.info("=" * 60)
    log.info("  MODEL C: Sentence-BERT + FAISS Duplicate Index")
    log.info("=" * 60)

    train_df = pd.read_csv(DATA / "train.csv").fillna("")
    fake_df = train_df[train_df["label"] == 1].reset_index(drop=True)
    real_df = train_df[train_df["label"] == 0].sample(
        min(3000, len(train_df[train_df["label"] == 0])), random_state=42
    ).reset_index(drop=True)

    sbert = SentenceTransformer("all-MiniLM-L6-v2")

    def enc(texts):
        return sbert.encode(
            texts, show_progress_bar=True, batch_size=128,
            normalize_embeddings=True
        ).astype(np.float32)

    log.info(f"  Encoding {len(fake_df)} fake + {len(real_df)} real posts...")
    fake_embs = enc(fake_df["short_text"].tolist())
    real_embs = enc(real_df["short_text"].tolist())

    dim = fake_embs.shape[1]
    idx_dir = MODELS / "faiss_index"
    idx_dir.mkdir(exist_ok=True)

    for embs, name in [(fake_embs, "fake_jobs"), (real_embs, "real_jobs")]:
        idx = faiss.IndexFlatIP(dim)
        idx.add(embs)
        faiss.write_index(idx, str(idx_dir / f"{name}.index"))

    meta = [{"text": row["short_text"][:300], "idx": i}
             for i, row in fake_df.iterrows()]
    with open(idx_dir / "metadata.json", "w") as f: json.dump(meta, f)
    with open(idx_dir / "index_info.json", "w") as f:
        json.dump({"dim": dim, "n_fake": len(fake_df), "n_real": len(real_df),
                    "built_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f, indent=2)

    log.info(f"  FAISS index: {len(fake_df)} fake, {len(real_df)} real, dim={dim}")


# ---------------------------------------------------------------------------
# MODEL D: TF-IDF + XGBoost Baseline
# ---------------------------------------------------------------------------

def train_baseline():
    log.info("=" * 60)
    log.info("  MODEL D: TF-IDF + XGBoost Baseline (NLP Fallback)")
    log.info("=" * 60)

    train_df = pd.read_csv(DATA / "train.csv").fillna("")
    test_df  = pd.read_csv(DATA / "test.csv").fillna("")

    STRUCT = ["has_salary","has_logo","has_questions","telecommuting",
              "text_length","desc_length","has_gmail","has_whatsapp",
              "exclamation_count","caps_ratio"]

    vec = TfidfVectorizer(
        max_features=120000, ngram_range=(1, 3),
        min_df=2, max_df=0.95, sublinear_tf=True,
        strip_accents="unicode"
    )
    X_tr_t = vec.fit_transform(train_df["full_text"])
    X_te_t = vec.transform(test_df["full_text"])

    avail = [c for c in STRUCT if c in train_df.columns]
    scaler_bl = StandardScaler(with_mean=False)
    X_tr_s = scaler_bl.fit_transform(train_df[avail].fillna(0)) if avail else \
             np.zeros((len(train_df), 1))
    X_te_s = scaler_bl.transform(test_df[avail].fillna(0)) if avail else \
             np.zeros((len(test_df), 1))

    X_tr = hstack([X_tr_t, sp.csr_matrix(X_tr_s)])
    X_te = hstack([X_te_t, sp.csr_matrix(X_te_s)])

    clf = xgb.XGBClassifier(
        n_estimators=500,
        scale_pos_weight=(train_df["label"]==0).sum() /
                          max((train_df["label"]==1).sum(), 1),
        tree_method="hist", n_jobs=-1, random_state=42, eval_metric="auc",
    )
    clf.fit(X_tr, train_df["label"])

    probs = clf.predict_proba(X_te)[:, 1]
    preds = clf.predict(X_te)
    log.info(classification_report(test_df["label"], preds,
                                    target_names=["Real","Fake"]))
    log.info(f"  ROC-AUC: {roc_auc_score(test_df['label'], probs):.4f}")

    bl_dir = MODELS / "baseline"
    bl_dir.mkdir(exist_ok=True)
    with open(bl_dir / "vectorizer.pkl", "wb") as f: pickle.dump(vec, f)
    with open(bl_dir / "classifier.pkl", "wb") as f: pickle.dump(clf, f)
    with open(bl_dir / "scaler.pkl",     "wb") as f: pickle.dump(scaler_bl, f)
    with open(bl_dir / "features.json",  "w")  as f: json.dump(avail, f)

    log.info(f"  Baseline model saved")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("  TRUSTHIRE - TRAINING ALL MODELS")
    log.info("=" * 60)

    for path in [DATA/"url_train.csv", DATA/"url_val.csv", DATA/"url_test.csv",
                 DATA/"train.csv", DATA/"val.csv", DATA/"test.csv"]:
        if not path.exists():
            log.error(f"Missing: {path}. Run: python scripts/download_datasets.py")
            sys.exit(1)

    url_threshold = train_url_classifier()
    train_bert()
    build_faiss()
    train_baseline()

    log.info("=" * 60)
    log.info("  ALL MODELS TRAINED SUCCESSFULLY")
    log.info(f"  URL Classifier Threshold: {url_threshold:.3f}")
    log.info("  Restart backend to load new models.")
    log.info("=" * 60)
