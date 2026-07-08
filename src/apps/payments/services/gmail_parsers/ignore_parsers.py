from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IgnoreMatch:
    category: str
    reason: str


class BaseIgnoreParser:
    category: str = "generic"
    keywords: tuple[str, ...] = ()

    def match(self, subject: str, body: str) -> IgnoreMatch | None:
        text = f"{subject} {body}".lower()
        for keyword in self.keywords:
            if keyword in text:
                return IgnoreMatch(category=self.category, reason=f"Matched keyword '{keyword}'.")
        return None


class CreditCardIgnoreParser(BaseIgnoreParser):
    category = "credit_card"
    keywords = (
        "credit card",
        "card statement",
        "minimum due",
        "card bill",
    )


class MarketingIgnoreParser(BaseIgnoreParser):
    category = "marketing"
    keywords = (
        "offer",
        "cashback",
        "sale",
        "promotional",
        "promotion",
        "promo",
        "limited period",
        "cross-sell",
        "cross sell",
        "pre-approved",
        "subscribe",
        "unsubscribe",
    )


class LoanIgnoreParser(BaseIgnoreParser):
    category = "loan"
    keywords = (
        "loan approved",
        "loan application",
        "personal loan",
        "home loan",
    )


class EMIIgnoreParser(BaseIgnoreParser):
    category = "emi"
    keywords = (
        "emi",
        "installment due",
        "standing instruction",
        "auto debit for emi",
    )
