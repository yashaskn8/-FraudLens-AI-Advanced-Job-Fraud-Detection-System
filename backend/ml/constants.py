"""
Shared constants for ML training and inference.
Centralizing these ensures the backend services and training scripts remain in sync.
"""

SUSPICIOUS_TLDS = {
    ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".click", ".work",
    ".online", ".site", ".website", ".tech", ".icu", ".vip", ".buzz",
    ".bond", ".rest", ".fyi", ".date", ".loans", ".finance", ".claims"
}

TRUSTED_TLDS = {
    ".com", ".org", ".net", ".edu", ".gov", ".mil", ".co.in", ".in",
    ".ac.in", ".gov.in", ".io", ".co", ".ai"
}

FREE_HOSTING = {
    "wix.com", "wixsite.com", "weebly.com", "wordpress.com", "blogspot.com",
    "site123.me", "yolasite.com", "jimdo.com", "webnode.com", "strikingly.com",
    "squarespace.com", "webflow.io", "netlify.app", "vercel.app", "github.io",
    "glitch.me", "000webhostapp.com", "infinityfree.net", "awardspace.com",
}

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly",
    "dlvr.it", "short.io", "tiny.cc", "lnkd.in", "rb.gy", "v.gd", "t2mio.com"
}

FRAUD_URL_KEYWORDS = {
    "earn", "income", "salary", "money", "free", "unlimited", "guaranteed", 
    "instant", "daily", "weekly", "lakhs", "crore", "registration", "fee", 
    "deposit", "scheme", "investment", "referral", "bonus", "cash", "pay"
}

PAYMENT_KEYWORDS = {
    "pay", "fee", "deposit", "invest", "register", "activation", 
    "subscription", "transfer", "upi", "gpay", "phonepe", "bank", "wallet"
}

LEGIT_EMPLOYERS = {
    "google", "microsoft", "amazon", "apple", "meta", "netflix", "uber", 
    "infosys", "wipro", "tcs", "hcl", "accenture", "ibm", "oracle", 
    "cognizant", "capgemini", "deloitte", "pwc", "ey", "kpmg", "techmahindra"
}

JOB_BOARDS = {
    "naukri", "linkedin", "indeed", "glassdoor", "monster", "timesjobs", 
    "shine", "internshala", "foundit", "upwork", "fiverr", "careerbuilder"
}
