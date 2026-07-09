"""
Synthetic data generator for TradeOps AI.
Produces 50 trades, ~200 execution logs, and 10 policy documents.
All data is deterministic (seeded) for reproducibility.
"""

import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

# ── Reference data ────────────────────────────────────────────────────────────

INSTRUMENTS = [
    ("AAPL", "EQUITY"), ("MSFT", "EQUITY"), ("GOOGL", "EQUITY"),
    ("AMZN", "EQUITY"), ("TSLA", "EQUITY"), ("JPM", "EQUITY"),
    ("GS", "EQUITY"),   ("BAC", "EQUITY"),  ("C", "EQUITY"),
    ("US10Y", "BOND"),  ("US2Y", "BOND"),   ("UK10Y", "BOND"),
    ("EUR/USD", "FX"),  ("GBP/USD", "FX"),  ("USD/JPY", "FX"),
    ("SPX_PUT_5500", "DERIVATIVE"), ("VIX_CALL_20", "DERIVATIVE"),
]

COUNTERPARTIES = [
    "Goldman Sachs", "Morgan Stanley", "JP Morgan", "Barclays",
    "Deutsche Bank", "UBS", "Credit Suisse", "Citigroup",
    "Bank of America", "HSBC",
]

BROKERS = [
    "Merrill Lynch", "Fidelity", "Charles Schwab", "Interactive Brokers",
    "TD Ameritrade", "Raymond James",
]

TRADERS = [f"TDR-{str(i).zfill(3)}" for i in range(1, 16)]

SYSTEMS = ["OMS", "CMS", "SWIFT", "CCP", "CUSTODY", "COMPLIANCE"]

FAILURE_TYPES = [
    "INSUFFICIENT_MARGIN",
    "SETTLEMENT_BREACH",
    "COUNTERPARTY_REJECTION",
    "INSTRUMENT_MISMATCH",
    "PRICE_TOLERANCE_BREACH",
    "DUPLICATE_TRADE",
    "COMPLIANCE_HOLD",
    "NETWORK_TIMEOUT",
    "CUSTODIAN_REJECTION",
    "CURRENCY_MISMATCH",
]

# ── Log sequence templates ─────────────────────────────────────────────────────

def _settled_logs(trade, base_time):
    """4 logs for a successfully settled trade."""
    steps = [
        (0,  "OMS",        "INFO",    "ORDER_RECEIVED",         f"Trade order received: {trade['quantity']} {trade['instrument']} @ {trade['price']} {trade['currency']}"),
        (2,  "COMPLIANCE", "INFO",    "COMPLIANCE_CHECK_PASSED",f"Pre-trade compliance check passed for counterparty {trade['counterparty']}"),
        (5,  "CMS",        "INFO",    "EXECUTION_CONFIRMED",    f"Execution confirmed by {trade['broker']}. Fill price: {trade['price']}"),
        (30, "CCP",        "INFO",    "SETTLEMENT_COMPLETED",   f"Settlement completed via CCP. Net position updated for {trade['counterparty']}"),
    ]
    return _build_logs(trade["trade_id"], base_time, steps)


def _pending_logs(trade, base_time):
    """2 logs for a trade still in progress."""
    steps = [
        (0, "OMS",  "INFO", "ORDER_RECEIVED",           f"Trade order received: {trade['quantity']} {trade['instrument']} @ {trade['price']} {trade['currency']}"),
        (3, "SWIFT","INFO", "SETTLEMENT_INITIATED",     f"Settlement instruction sent to {trade['counterparty']} via SWIFT MT541"),
    ]
    return _build_logs(trade["trade_id"], base_time, steps)


def _failed_logs(trade, base_time):
    """5 logs for a failed trade — sequence depends on failure type."""
    ft = trade["failure_reason"]

    if ft == "INSUFFICIENT_MARGIN":
        steps = [
            (0,  "OMS",        "INFO",    "ORDER_RECEIVED",        f"Trade order received: {trade['quantity']} {trade['instrument']} @ {trade['price']}"),
            (1,  "CMS",        "WARNING", "MARGIN_CHECK_INITIATED", f"Initiating margin check for notional {trade['notional_value']:,.2f} {trade['currency']}"),
            (2,  "CMS",        "ERROR",   "MARGIN_CHECK_FAILED",   f"Margin shortfall detected: required {trade['notional_value'] * 0.12:,.2f}, available {trade['notional_value'] * 0.05:,.2f}"),
            (3,  "OMS",        "ERROR",   "ORDER_REJECTED",        f"Order rejected due to insufficient margin. Shortfall: {trade['notional_value'] * 0.07:,.2f} {trade['currency']}"),
            (4,  "COMPLIANCE", "WARNING", "INCIDENT_LOGGED",       f"Margin breach incident logged. Trader {trade['trader_id']} notified."),
        ]

    elif ft == "SETTLEMENT_BREACH":
        steps = [
            (0,   "OMS",     "INFO",    "ORDER_RECEIVED",          f"Trade order received for {trade['instrument']}"),
            (2,   "SWIFT",   "INFO",    "SETTLEMENT_INITIATED",    f"Settlement instruction dispatched to custodian for T+2 settlement"),
            (180, "SWIFT",   "WARNING", "SETTLEMENT_OVERDUE",      f"Settlement window approaching expiry. No confirmation from {trade['counterparty']}"),
            (360, "CCP",     "ERROR",   "SETTLEMENT_FAILED",       f"Settlement failed: T+2 deadline breached. Trade entered buy-in process"),
            (365, "OMS",     "ERROR",   "TRADE_FAILED",            f"Trade marked FAILED. Buy-in penalty applicable per CSDR Article 7"),
        ]

    elif ft == "COUNTERPARTY_REJECTION":
        steps = [
            (0,  "OMS",   "INFO",    "ORDER_RECEIVED",            f"Trade order received: {trade['quantity']} {trade['instrument']}"),
            (2,  "SWIFT", "INFO",    "COUNTERPARTY_NOTIFIED",     f"Settlement notice sent to {trade['counterparty']} via SWIFT MT515"),
            (15, "SWIFT", "ERROR",   "COUNTERPARTY_REJECTED",     f"{trade['counterparty']} rejected settlement: unmatched trade details"),
            (17, "OMS",   "WARNING", "RECONCILIATION_ATTEMPTED",  f"Attempting trade reconciliation with {trade['counterparty']} operations desk"),
            (45, "OMS",   "ERROR",   "RECONCILIATION_FAILED",     f"Reconciliation failed. Trade voided after counterparty declined amendment"),
        ]

    elif ft == "INSTRUMENT_MISMATCH":
        steps = [
            (0,  "OMS",     "INFO",    "ORDER_RECEIVED",         f"Trade order received for ISIN mismatch on {trade['instrument']}"),
            (1,  "CMS",     "WARNING", "INSTRUMENT_LOOKUP",      f"Instrument lookup returned ambiguous ISIN for {trade['instrument']}"),
            (2,  "CMS",     "ERROR",   "ISIN_MISMATCH_DETECTED", f"ISIN mismatch: order ISIN does not match CCP reference data"),
            (5,  "OMS",     "ERROR",   "ORDER_REJECTED",         f"Order rejected: instrument reference data conflict. Manual review required"),
            (10, "CUSTODY", "WARNING", "INCIDENT_RAISED",        f"Instrument mismatch incident raised. Reference data team notified"),
        ]

    elif ft == "PRICE_TOLERANCE_BREACH":
        steps = [
            (0,  "OMS",  "INFO",    "ORDER_RECEIVED",            f"Trade order received @ {trade['price']} {trade['currency']}"),
            (1,  "OMS",  "INFO",    "PRICE_VALIDATION",          f"Initiating price tolerance check against market mid"),
            (2,  "OMS",  "ERROR",   "PRICE_TOLERANCE_EXCEEDED",  f"Execution price {trade['price']} deviates >2% from market mid. Breach threshold exceeded"),
            (3,  "OMS",  "ERROR",   "ORDER_HALTED",              f"Order halted pending trader confirmation. Auto-reject triggered after 30s timeout"),
            (35, "OMS",  "ERROR",   "ORDER_REJECTED",            f"Trade rejected: price tolerance breach unacknowledged within window"),
        ]

    elif ft == "DUPLICATE_TRADE":
        steps = [
            (0,  "OMS",  "INFO",    "ORDER_RECEIVED",      f"Trade order received: {trade['quantity']} {trade['instrument']}"),
            (1,  "OMS",  "WARNING", "DUPLICATE_CHECK",     f"Running duplicate detection against orders in last 60 minutes"),
            (1,  "OMS",  "ERROR",   "DUPLICATE_DETECTED",  f"Duplicate trade detected: matches existing order with same instrument, quantity, counterparty"),
            (2,  "OMS",  "ERROR",   "ORDER_REJECTED",      f"Trade rejected as duplicate. Original order reference retained"),
            (3,  "COMPLIANCE", "INFO", "AUDIT_LOGGED",     f"Duplicate rejection logged in audit trail per EMIR reporting requirements"),
        ]

    elif ft == "COMPLIANCE_HOLD":
        steps = [
            (0,   "OMS",        "INFO",    "ORDER_RECEIVED",        f"Trade order received for {trade['counterparty']}"),
            (1,   "COMPLIANCE", "INFO",    "COMPLIANCE_CHECK",      f"Running pre-trade compliance: sanctions, position limits, insider lists"),
            (3,   "COMPLIANCE", "ERROR",   "COMPLIANCE_HOLD_PLACED",f"Compliance hold placed: {trade['counterparty']} flagged in enhanced due diligence list"),
            (60,  "COMPLIANCE", "WARNING", "HOLD_UNDER_REVIEW",     f"Compliance team reviewing hold. Trade execution suspended"),
            (240, "COMPLIANCE", "ERROR",   "TRADE_BLOCKED",         f"Trade blocked by compliance officer. Regulatory notification required within 24h"),
        ]

    elif ft == "NETWORK_TIMEOUT":
        steps = [
            (0,   "OMS",   "INFO",  "ORDER_RECEIVED",         f"Trade order received and validated"),
            (3,   "SWIFT", "INFO",  "SETTLEMENT_INITIATED",   f"SWIFT MT541 dispatched to {trade['counterparty']} custodian"),
            (33,  "SWIFT", "WARNING","CONNECTION_TIMEOUT",    f"SWIFT connection timeout after 30s. Retrying (attempt 1/3)"),
            (93,  "SWIFT", "WARNING","RETRY_FAILED",          f"SWIFT retry attempts exhausted. No acknowledgment from correspondent bank"),
            (95,  "OMS",   "ERROR", "SETTLEMENT_FAILED",      f"Settlement failed: network timeout. Trade flagged for manual intervention"),
        ]

    elif ft == "CUSTODIAN_REJECTION":
        steps = [
            (0,  "OMS",     "INFO",  "ORDER_RECEIVED",          f"Trade order received for {trade['instrument']}"),
            (5,  "CUSTODY", "INFO",  "CUSTODY_INSTRUCTION_SENT",f"DvP instruction sent to custodian for {trade['notional_value']:,.2f} {trade['currency']}"),
            (20, "CUSTODY", "ERROR", "CUSTODIAN_REJECTED",      f"Custodian rejected instruction: insufficient securities in account for delivery"),
            (22, "CUSTODY", "WARNING","STOCK_BORROW_ATTEMPTED", f"Attempting stock borrow to cover short position for settlement"),
            (45, "OMS",     "ERROR", "SETTLEMENT_FAILED",       f"Settlement failed: custodian rejection. Stock borrow unavailable"),
        ]

    else:  # CURRENCY_MISMATCH
        steps = [
            (0,  "OMS",  "INFO",    "ORDER_RECEIVED",          f"Trade order received in {trade['currency']}"),
            (1,  "CMS",  "INFO",    "CURRENCY_VALIDATION",     f"Validating currency against counterparty settlement account"),
            (2,  "CMS",  "ERROR",   "CURRENCY_MISMATCH",       f"Currency mismatch: order in {trade['currency']} but counterparty account denominated in EUR"),
            (5,  "CMS",  "WARNING", "FX_CONVERSION_ATTEMPTED", f"Attempting automatic FX conversion via treasury desk"),
            (20, "OMS",  "ERROR",   "CONVERSION_FAILED",       f"FX conversion failed: rate unavailable. Trade rejected pending manual currency instruction"),
        ]

    return _build_logs(trade["trade_id"], base_time, steps)


def _build_logs(trade_id, base_time, steps):
    logs = []
    for minutes_offset, system, severity, event_type, message in steps:
        logs.append({
            "trade_id":   trade_id,
            "timestamp":  base_time + timedelta(minutes=minutes_offset),
            "event_type": event_type,
            "message":    message,
            "severity":   severity,
            "system":     system,
        })
    return logs


# ── Trade generation ──────────────────────────────────────────────────────────

def generate_trades():
    trades = []
    base_date = datetime(2024, 9, 1)

    # 20 FAILED, 20 SETTLED, 10 PENDING
    statuses = (
        [("FAILED", ft) for ft in FAILURE_TYPES * 2] +   # 20 failed (each type twice)
        [("SETTLED", None)] * 20 +
        [("PENDING", None)] * 10
    )
    random.shuffle(statuses)

    for i, (status, failure_reason) in enumerate(statuses, start=1):
        instrument, instrument_type = random.choice(INSTRUMENTS)
        quantity = random.choice([100, 250, 500, 1000, 2500, 5000])
        price = round(random.uniform(10.0, 500.0), 2)
        trade_date = base_date + timedelta(days=random.randint(0, 60))

        trades.append({
            "trade_id":        f"TRD-{str(i).zfill(3)}",
            "trade_date":      trade_date.date(),
            "settlement_date": (trade_date + timedelta(days=2)).date(),
            "status":          status,
            "instrument":      instrument,
            "instrument_type": instrument_type,
            "quantity":        quantity,
            "price":           price,
            "notional_value":  round(quantity * price, 2),
            "currency":        random.choice(["USD", "EUR", "GBP"]),
            "counterparty":    random.choice(COUNTERPARTIES),
            "trader_id":       random.choice(TRADERS),
            "broker":          random.choice(BROKERS),
            "failure_reason":  failure_reason,
            "created_at":      trade_date.replace(
                hour=random.randint(8, 16),
                minute=random.randint(0, 59)
            ),
        })

    return trades


# ── Log generation ────────────────────────────────────────────────────────────

def generate_logs(trades):
    logs = []
    log_counter = 1

    for trade in trades:
        base_time = trade["created_at"]

        if trade["status"] == "SETTLED":
            entries = _settled_logs(trade, base_time)
        elif trade["status"] == "PENDING":
            entries = _pending_logs(trade, base_time)
        else:
            entries = _failed_logs(trade, base_time)

        for entry in entries:
            entry["log_id"] = f"LOG-{str(log_counter).zfill(4)}"
            log_counter += 1
            logs.append(entry)

    return logs


# ── Policy documents ──────────────────────────────────────────────────────────

POLICY_DOCUMENTS = [
    {
        "doc_id":  "POL-001",
        "title":   "Trade Settlement Policy",
        "content": """
Trade Settlement Policy — Version 3.2

1. STANDARD SETTLEMENT CYCLES
All equity and bond trades settle on a T+2 basis (trade date plus two business days) in accordance
with CSDR regulations. FX spot trades settle T+2 and FX forwards settle on the agreed value date.
Derivatives settle per the relevant exchange or bilateral agreement.

2. SETTLEMENT FAILURE DEFINITION
A trade is classified as a settlement failure when the intended delivery of securities or cash has
not occurred by the end of the intended settlement date. The Operations team must be notified
within 1 hour of a confirmed settlement fail.

3. SETTLEMENT MONITORING
The settlement team monitors all pending trades via the CCP dashboard and SWIFT MT548 status
messages. Trades not confirmed by 15:00 local time on settlement date are escalated to the
Settlement Supervisor.

4. BUY-IN PROCEDURES
Under CSDR Article 7, a buy-in process is triggered after 4 business days (T+6 for equities, T+7
for bonds) if settlement has not occurred. The counterparty failing to deliver is liable for the
buy-in cost plus a cash penalty calculated daily.

5. PENALTIES
Daily cash penalties apply from the intended settlement date: 1 basis point of notional for liquid
instruments, 0.5 bp for illiquid instruments, and 0.5 bp for sovereign bonds.
""",
    },
    {
        "doc_id":  "POL-002",
        "title":   "Failed Trade Resolution Procedure",
        "content": """
Failed Trade Resolution Procedure — Version 2.1

1. IMMEDIATE RESPONSE (0–1 HOUR)
Upon detection of a trade failure, the Operations Analyst must:
  a) Record the failure in the incident management system within 30 minutes.
  b) Identify the failure category: pre-settlement, settlement, or post-settlement.
  c) Notify the responsible trader and their desk head via the alerting system.
  d) Place a hold on any related trades with the same counterparty pending investigation.

2. INVESTIGATION PHASE (1–4 HOURS)
The investigation must determine root cause using the following data sources:
  - OMS execution logs (event sequence and timestamps)
  - SWIFT message archive (MT515, MT541, MT548 confirmations)
  - CCP matching status report
  - Counterparty confirmation records

3. ESCALATION MATRIX
  - Notional < $1M:      Operations Analyst resolves independently
  - Notional $1M–$10M:   Operations Supervisor sign-off required
  - Notional > $10M:     Head of Operations + Risk desk notification mandatory
  - Regulatory impact:   Compliance Officer must be notified within 2 hours

4. RESOLUTION AND CLOSE-OUT
All failed trades must have a documented resolution record including: root cause, corrective
action taken, parties notified, and preventive measures. Resolution records are retained for
7 years per regulatory requirements.

5. REPORTING
Failed trades are reported to senior management daily and to the regulator as required under
EMIR/MiFID II transaction reporting obligations.
""",
    },
    {
        "doc_id":  "POL-003",
        "title":   "Counterparty Risk Management Policy",
        "content": """
Counterparty Risk Management Policy — Version 4.0

1. COUNTERPARTY ONBOARDING
All new counterparties must complete KYC/AML screening, credit assessment, and legal
documentation (ISDA Master Agreement or equivalent) before any trade is executed.

2. EXPOSURE LIMITS
Counterparty exposure limits are set by the Credit Risk team and reviewed quarterly:
  - Tier 1 (investment grade, AA+): Up to $500M gross exposure
  - Tier 2 (investment grade, A–BBB): Up to $200M gross exposure
  - Tier 3 (sub-investment grade): Up to $50M, Credit desk pre-approval required

3. COUNTERPARTY REJECTION HANDLING
When a counterparty rejects a trade or fails to confirm settlement, the following steps apply:
  a) Contact the counterparty operations desk immediately to identify the discrepancy.
  b) Perform a trade-by-trade reconciliation against the counterparty's records.
  c) If unresolved within 2 hours, escalate to the Counterparty Relationship Manager.
  d) For repeated rejections (>3 in 30 days), initiate a formal counterparty review.

4. DEFAULT PROCEDURES
In the event of counterparty default:
  - Immediately net all outstanding positions under the ISDA close-out netting provisions.
  - Notify the Credit Risk and Legal teams within 1 hour.
  - File regulatory notification as required.
  - Commence recovery of posted collateral.

5. COLLATERAL MANAGEMENT
Bilateral trades require initial margin posting per EMIR margining rules. Variation margin
is exchanged daily. Margin disputes must be resolved within 1 business day.
""",
    },
    {
        "doc_id":  "POL-004",
        "title":   "Margin and Collateral Requirements",
        "content": """
Margin and Collateral Requirements Policy — Version 2.3

1. INITIAL MARGIN
Initial margin is required for all non-cleared OTC derivatives and certain cleared products.
The margin requirement is calculated using a 99% 10-day VaR model, with a floor of:
  - Equities:     15% of notional
  - Fixed Income: 8% of notional
  - FX:           6% of notional
  - Derivatives:  20% of notional (or exchange-mandated rate if higher)

2. MARGIN BREACH PROCEDURE
When a margin shortfall is detected:
  a) OMS generates an automatic margin call within 5 minutes of detection.
  b) Counterparty has until 12:00 noon the following business day to post collateral.
  c) If margin call is not met, the firm may close out positions to reduce exposure.
  d) All margin breaches must be logged in the risk management system.

3. ELIGIBLE COLLATERAL
  - Cash (USD, EUR, GBP, JPY): Accepted at 100% value
  - G10 Government bonds < 1 year: 98% of market value
  - G10 Government bonds 1–10 years: 95% of market value
  - Investment grade corporate bonds: 90% of market value
  - Equities (S&P 500 / FTSE 100): 85% of market value

4. INSUFFICIENT MARGIN HANDLING
Trades flagged for insufficient margin must not proceed to execution. The trader must either:
  a) Reduce the trade size to within available margin, or
  b) Post additional collateral before order submission, or
  c) Obtain Credit desk pre-approval for a temporary limit exception (max 48 hours).

5. VARIATION MARGIN
Daily mark-to-market variation margin is exchanged by 10:00 AM on the next business day.
Disputes on VM amounts must be raised by 11:00 AM on the same day.
""",
    },
    {
        "doc_id":  "POL-005",
        "title":   "Trade Compliance and Regulatory Policy",
        "content": """
Trade Compliance and Regulatory Policy — Version 5.1

1. PRE-TRADE COMPLIANCE CHECKS
All orders must pass automated pre-trade checks before execution:
  - Sanctions screening (OFAC, EU, UN lists): real-time, hard block
  - Position limit checks (internal and regulatory): hard block if breached
  - Insider trading / restricted list check: hard block
  - Best execution obligation verification (MiFID II Article 27)

2. COMPLIANCE HOLD PROCEDURES
When a compliance hold is placed on a trade:
  a) The trade is immediately suspended and cannot be executed.
  b) The compliance officer responsible for the hold is alerted within 5 minutes.
  c) The hold must be reviewed within 4 business hours.
  d) The trader and desk head are notified of the hold (but not the reason, if sensitive).
  e) If the hold is not resolved within 24 hours, it is escalated to the Chief Compliance Officer.

3. REGULATORY REPORTING
  - MiFID II: All trades must be reported to the ARM within T+1
  - EMIR: OTC derivatives reported to trade repository within T+1
  - Dodd-Frank: USD-denominated swaps reported to SDR on trade date
  - CFTC Large Trader: Positions above reportable thresholds reported weekly

4. SANCTIONS VIOLATIONS
Any potential sanctions violation must be reported to the Chief Compliance Officer and Legal
within 1 hour of detection. Trading with sanctioned entities is strictly prohibited and may
result in regulatory penalties and criminal liability.

5. RECORD KEEPING
All trade records, communications, and compliance decisions must be retained for a minimum
of 7 years in an immutable audit trail.
""",
    },
    {
        "doc_id":  "POL-006",
        "title":   "Settlement Fail Penalty Policy",
        "content": """
Settlement Fail Penalty Policy — Version 1.4

1. CSDR CASH PENALTIES (Effective February 2022)
Under the Central Securities Depositories Regulation (EU) 2014/909, cash penalties apply
automatically to settlement fails in EU/EEA markets:
  - Liquid shares (ESMA list):     1.0 basis point per day of notional
  - Other shares / ETFs:           0.5 basis points per day
  - SME growth market instruments: 0.25 basis points per day
  - Government bonds / covered bonds: 0.10 basis points per day
  - Corporate bonds:               0.20 basis points per day

2. PENALTY CALCULATION
Penalties are calculated on the failed quantity and the reference price (previous day close
or VWAP). Penalties accrue from intended settlement date until the fail is resolved or a
buy-in is initiated.

3. INTERNAL COST ALLOCATION
Penalties received from the CSD are charged to the responsible desk. The Operations
team allocates penalties based on root cause analysis:
  - Trader error: charged to the trading desk P&L
  - Operations error: charged to Operations cost centre
  - Counterparty failure: recovery proceedings initiated against counterparty

4. BUY-IN PROCESS
If a fail persists beyond the extension period (4 business days for equities, 7 for bonds):
  a) The receiving participant may trigger a mandatory buy-in.
  b) The CSD appoints a buy-in agent to purchase the securities in the market.
  c) Any excess cost vs. original trade price is borne by the failing party.
  d) A cash compensation is paid to the receiving party if buy-in is unsuccessful.

5. DISPUTE RESOLUTION
Penalty disputes must be raised within 3 business days of notification. Disputes are
handled by the Operations Reconciliation team and resolved within 10 business days.
""",
    },
    {
        "doc_id":  "POL-007",
        "title":   "Trade Amendment and Cancellation Policy",
        "content": """
Trade Amendment and Cancellation Policy — Version 2.0

1. AMENDMENT ELIGIBILITY
Trade amendments are permitted only in the following circumstances:
  - Clerical errors discovered before settlement confirmation
  - Counterparty agreement to modified terms (bilateral amendment)
  - Regulatory directive requiring amendment
  Amendments to price, quantity, or counterparty on settled trades are not permitted.

2. AMENDMENT WINDOW
  - Equity / bond trades: amendments accepted until 17:00 on trade date (T)
  - FX trades: amendments accepted until 2 hours before settlement cut-off
  - Derivatives: per ISDA protocol, within agreed amendment period

3. APPROVAL REQUIREMENTS
  - Amendments < $500K impact: Desk Head approval
  - Amendments $500K–$5M impact: Operations Supervisor + Risk approval
  - Amendments > $5M impact: Head of Trading + CFO approval required
  All approvals must be documented in the OMS before the amendment is processed.

4. CANCELLATION PROCEDURE
Trade cancellations require:
  a) Written reason and supporting documentation
  b) Counterparty confirmation of cancellation agreement
  c) Approval per the amendment approval matrix above
  d) Regulatory reporting update if the trade was already reported

5. DUPLICATE TRADE HANDLING
Duplicate trades detected by the OMS are automatically rejected. If a duplicate is identified
post-execution, it must be cancelled by mutual agreement with the counterparty. The later-
timestamped trade is cancelled unless both parties agree otherwise. All duplicate incidents
are reported to Compliance.
""",
    },
    {
        "doc_id":  "POL-008",
        "title":   "Operational Risk Management Policy",
        "content": """
Operational Risk Management Policy — Version 3.1

1. OPERATIONAL RISK FRAMEWORK
The firm manages operational risk using the Basel III/IV Advanced Measurement Approach.
All operational risk events (losses, near-misses, and incidents) must be captured in the
Operational Risk Management System (ORMS) within 24 hours of discovery.

2. INCIDENT CLASSIFICATION
  - Severity 1 (Critical): Financial loss > $1M, regulatory breach, or market-wide impact
  - Severity 2 (High):     Financial loss $100K–$1M, process failure affecting multiple trades
  - Severity 3 (Medium):   Financial loss $10K–$100K, single trade affected, recoverable
  - Severity 4 (Low):      Financial loss < $10K, near-miss, no customer impact

3. SYSTEM FAILURE PROCEDURES
When a trading system (OMS, CMS, SWIFT gateway) experiences an outage:
  a) The Technology team must notify Operations within 10 minutes of confirmed outage.
  b) Manual trade processing procedures are activated immediately (see BCP policy POL-009).
  c) All trades in-flight at time of outage are placed in a pending/suspended state.
  d) System recovery target: RTO 2 hours for Severity 1, 4 hours for Severity 2.

4. NETWORK TIMEOUT HANDLING
SWIFT and CCP connection timeouts are monitored by the middleware team. Standard procedure:
  - Timeout threshold: 30 seconds for SWIFT, 10 seconds for CCP API
  - Auto-retry: 3 attempts at 60-second intervals
  - After 3 failed retries: alert raised to Operations, manual intervention initiated
  - Trades awaiting settlement during timeout are held in PENDING status until confirmed

5. THIRD-PARTY RISK
Critical dependencies (CCPs, custodians, prime brokers) are subject to annual third-party
risk assessments. Contingency arrangements must be maintained for all Tier 1 dependencies.
""",
    },
    {
        "doc_id":  "POL-009",
        "title":   "Business Continuity and Disaster Recovery Policy",
        "content": """
Business Continuity and Disaster Recovery Policy — Version 2.2

1. SCOPE
This policy covers all critical trading and settlement infrastructure, including OMS, CMS,
SWIFT gateway, CCP connectivity, reference data systems, and compliance platforms.

2. RECOVERY OBJECTIVES
  - RTO (Recovery Time Objective):  2 hours for Tier 1 systems, 4 hours for Tier 2
  - RPO (Recovery Point Objective): 15 minutes maximum data loss for all trading systems

3. BCP TRIGGER CONDITIONS
BCP activation is required when:
  - Primary data centre is unavailable for > 30 minutes
  - Primary OMS is unavailable for > 1 hour
  - SWIFT connectivity is lost for > 2 hours
  - A cyber incident affects trading or settlement platforms

4. FAILOVER PROCEDURES
  - Automated failover to DR site for database and application servers
  - SWIFT BIC routing switched to DR connectivity within 1 hour
  - All in-flight trades are reconciled against DR snapshot before resuming
  - Manual trade booking procedures available as fallback (see Operations Manual §4.3)

5. COMMUNICATION PLAN
  - Incident Commander designated from senior Operations leadership
  - All staff notified via emergency contact tree within 15 minutes of BCP activation
  - Regulators notified within 2 hours of any prolonged outage
  - Client notifications coordinated by Relationship Management team

6. TESTING
BCP is tested in full at least twice annually. Partial failover tests are conducted quarterly.
Test results and any remediation actions are reported to the Board Risk Committee.
""",
    },
    {
        "doc_id":  "POL-010",
        "title":   "Reference Data and Instrument Validation Policy",
        "content": """
Reference Data and Instrument Validation Policy — Version 1.2

1. INSTRUMENT REFERENCE DATA
All tradeable instruments must be registered in the firm's Security Master File (SMF) before
they can be traded. The SMF is the authoritative source for:
  - ISIN, CUSIP, SEDOL identifiers
  - Instrument type, currency, and exchange
  - Settlement convention (T+1, T+2, T+3)
  - Price source and tick size
  - Regulatory classification (MiFID II instrument type)

2. ISIN VALIDATION
Pre-trade ISIN validation is mandatory. The OMS checks the submitted ISIN against:
  a) The internal SMF
  b) The CCP's reference data service (real-time)
  c) The relevant CSD's instrument database
  A mismatch between any two sources results in an automatic order hold pending review.

3. INSTRUMENT MISMATCH HANDLING
When an ISIN or instrument attribute mismatch is detected:
  a) The order is immediately rejected with error code REF-001 (ISIN_MISMATCH).
  b) The Reference Data team is alerted to investigate the discrepancy.
  c) The trader is notified and must resubmit with the correct instrument details.
  d) If the SMF entry is incorrect, an emergency SMF update is processed within 2 hours.
  e) A root cause report is filed for any mismatch involving live market instruments.

4. CURRENCY VALIDATION
Trade currency must match the settlement account currency or an approved FX conversion
arrangement must be in place. Automatic currency conversion is available for USD, EUR, GBP,
and JPY pairs. All other currency conversions require treasury desk pre-approval.

5. PRICE TOLERANCE CHECKS
Execution prices are validated against real-time market data:
  - Equities:    ±2% from last trade price or NBBO mid
  - Bonds:       ±1% from evaluated mid price
  - FX:          ±0.5% from spot mid
  - Derivatives: ±3% from theoretical fair value
  Orders breaching tolerance are auto-halted for 30 seconds pending trader acknowledgment.
  If unacknowledged, the order is automatically rejected.
""",
    },
]


# ── Public interface ──────────────────────────────────────────────────────────

def get_all_data():
    """Return (trades, logs, policy_documents) as plain Python dicts."""
    trades = generate_trades()
    logs   = generate_logs(trades)
    return trades, logs, POLICY_DOCUMENTS


if __name__ == "__main__":
    trades, logs, policies = get_all_data()
    print(f"Trades:   {len(trades)}")
    print(f"Logs:     {len(logs)}")
    print(f"Policies: {len(policies)}")

    failed = [t for t in trades if t["status"] == "FAILED"]
    print(f"\nFailed trades ({len(failed)}):")
    for t in failed[:5]:
        print(f"  {t['trade_id']} — {t['failure_reason']} — {t['instrument']}")
    print("  ...")
