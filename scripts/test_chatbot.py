import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.chatbot import process_message  # noqa: E402

cases = [
    "bhai mujhe kashmiri gate se aiims jaana hai kaise jau",
    "kashmiri gate se aiims kitna time lagta hai",
    "kashmiri gate ke baare me batao",
    "abhi live traffic hai kya",
    "cricket score batao",
    "hi",
    "Route from Rohini Sec 22 Terminal to Azadpur Terminal",
    "Tell me about Lakhhi Ram Park",
    "poem about cats",
]
for c in cases:
    reply = process_message(c)
    print("Q:", c)
    print("A:", reply[:340].replace("\n", " | "))
    print("-" * 70)
