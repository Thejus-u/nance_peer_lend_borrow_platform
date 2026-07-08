from __future__ import annotations

from dataclasses import dataclass

from apps.payments.services.gmail_parsers.base import ParsedTransaction
from apps.payments.services.gmail_parsers.ignore_parsers import (
    BaseIgnoreParser,
    CreditCardIgnoreParser,
    EMIIgnoreParser,
    IgnoreMatch,
    LoanIgnoreParser,
    MarketingIgnoreParser,
)
from apps.payments.services.gmail_parsers.transaction_parsers import (
    ATMParser,
    CreditParser,
    DebitParser,
    NEFTParser,
    RTGSParser,
    UPIParser,
)


@dataclass(frozen=True)
class ParseOutcome:
    ignored: bool
    ignored_category: str | None
    transaction: ParsedTransaction | None


class GmailTransactionParserPipeline:
    """Orchestrates ignore filters and transaction parsers for Gmail message content."""

    def __init__(self) -> None:
        self.ignore_parsers: tuple[BaseIgnoreParser, ...] = (
            CreditCardIgnoreParser(),
            MarketingIgnoreParser(),
            LoanIgnoreParser(),
            EMIIgnoreParser(),
        )
        self.transaction_parsers = (
            UPIParser(),
            NEFTParser(),
            RTGSParser(),
            ATMParser(),
            DebitParser(),
            CreditParser(),
        )

    def parse(self, *, subject: str, body: str) -> ParseOutcome:
        ignore_match = self._check_ignore(subject=subject, body=body)
        if ignore_match is not None:
            return ParseOutcome(
                ignored=True,
                ignored_category=ignore_match.category,
                transaction=None,
            )

        for parser in self.transaction_parsers:
            if parser.can_parse(subject, body):
                return ParseOutcome(
                    ignored=False,
                    ignored_category=None,
                    transaction=parser.parse(subject, body),
                )

        return ParseOutcome(ignored=False, ignored_category=None, transaction=None)

    def _check_ignore(self, *, subject: str, body: str) -> IgnoreMatch | None:
        for parser in self.ignore_parsers:
            match = parser.match(subject=subject, body=body)
            if match is not None:
                return match
        return None
