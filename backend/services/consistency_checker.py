"""
Consistency Checker Service
Checks internal consistency of a job posting using rule-based heuristics.
"""
from dataclasses import dataclass, field
from typing import Optional
import re


@dataclass
class ConsistencyCheckResult:
    salary_consistent: bool
    location_consistent: bool
    requirements_consistent: bool
    contact_info_present: bool
    consistency_score: float
    flags: list = field(default_factory=list)


def check_salary_consistency(description: str, title: str) -> tuple:
    """Check if salary claims are realistic for the job title."""
    flags = []
    text = description.lower()

    # Detect unrealistic salary claims
    salary_patterns = re.findall(r'(?:rs\.?|₹|inr)\s*(\d[\d,]*)', text)
    monthly_amounts = []
    for s in salary_patterns:
        amount = int(s.replace(",", ""))
        monthly_amounts.append(amount)

    if monthly_amounts:
        max_salary = max(monthly_amounts)
        entry_level_keywords = ["intern", "fresher", "entry", "junior", "trainee"]
        is_entry = any(kw in title.lower() for kw in entry_level_keywords)
        if is_entry and max_salary > 100000:
            flags.append(
                f"Salary of ₹{max_salary:,} is unrealistically high for an entry-level position"
            )
            return False, flags
        if max_salary > 500000:
            flags.append(
                f"Claimed monthly salary of ₹{max_salary:,} is suspiciously high"
            )
            return False, flags

    return True, flags


def check_contact_consistency(description: str) -> tuple:
    """Check for suspicious contact patterns."""
    flags = []
    text = description.lower()

    # WhatsApp-only contact is suspicious
    if "whatsapp" in text and not any(w in text for w in ["email", "apply", "portal", "website"]):
        flags.append("Job only provides WhatsApp contact — no official application channel")
        return False, flags

    # Telegram contact
    if "telegram" in text:
        flags.append("Job uses Telegram for communication — uncommon for legitimate companies")
        return False, flags

    return True, flags


async def check_consistency(
    description: str,
    title: str = "",
    company_name: str = "",
) -> ConsistencyCheckResult:
    """Run all consistency checks on the posting."""
    all_flags = []

    salary_ok, salary_flags = check_salary_consistency(description, title)
    all_flags.extend(salary_flags)

    contact_ok, contact_flags = check_contact_consistency(description)
    all_flags.extend(contact_flags)

    # Check requirements vs benefits mismatch
    text_lower = description.lower()
    requirements_ok = True
    if "no experience" in text_lower and "senior" in title.lower():
        all_flags.append("Senior position but requires no experience — inconsistent")
        requirements_ok = False

    # Location consistency
    location_ok = True
    if "remote" in text_lower and "office" in text_lower and "hybrid" not in text_lower:
        all_flags.append("Posting mentions both remote and office without clarification")
        location_ok = False

    # Score calculation
    checks = [salary_ok, contact_ok, requirements_ok, location_ok]
    consistency_score = sum(checks) / len(checks)

    return ConsistencyCheckResult(
        salary_consistent=salary_ok,
        location_consistent=location_ok,
        requirements_consistent=requirements_ok,
        contact_info_present=contact_ok,
        consistency_score=consistency_score,
        flags=all_flags,
    )
