import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000/api/v1/scan"

TEST_CASES = [
    {
        "name": "UK Job (Tesco)",
        "payload": {
            "url": "https://www.tesco-careers.com/jobs/748392",
            "description": "Software Engineer at Tesco UK. Full-time position in Welwyn Garden City."
        }
    },
    {
        "name": "AU Job (Telstra)",
        "payload": {
            "url": "https://careers.telstra.com/job-details?jobId=123456",
            "description": "Network Engineer at Telstra Melbourne. AUD 120,000 per year."
        }
    },
    {
        "name": "US Job (Google)",
        "payload": {
            "url": "https://www.google.com/about/careers/applications/jobs/results/987654321",
            "description": "Product Manager at Google Mountain View, CA. SEC EDGAR verified company."
        }
    },
    {
        "name": "Multilingual Scam (Indonesian)",
        "payload": {
            "url": "http://loker-indomaret-palsu.com/apply",
            "description": "Lowongan kerja Indomaret. Gaji harian 500rb. Hubungi WA 0812345678 untuk test."
        }
    }
]

def run_tests():
    print(f"{'Test Name':<30} | {'Status':<10} | {'Country':<10} | {'Registry':<20} | {'Score'}")
    print("-" * 90)
    for tc in TEST_CASES:
        try:
            resp = requests.post(BASE_URL, json=tc["payload"], timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                company = data.get("company_details") or {}
                country = company.get("detected_country", "??")
                registry = company.get("registry_used", "??")
                score = data.get("trust_score", 0)
                print(f"{tc['name']:<30} | {'SUCCESS':<10} | {country:<10} | {registry:<20} | {score}")
            else:
                print(f"{tc['name']:<30} | {f'ERROR {resp.status_code}':<10} | {'-':<10} | {'-':<20} | -")
        except Exception as e:
            print(f"{tc['name']:<30} | {'FAILED':<10} | {'-':<10} | {'-':<20} | {str(e)}")

if __name__ == "__main__":
    run_tests()
