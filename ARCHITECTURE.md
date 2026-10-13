# Architecture and trade-offs

## 1. Append-only at scale

**What breaks first.** The replay. To find the current balance the ledger
checks all the previous data every time, so the work grows with everything
ever recorded.

**Where state piles up.** In memory. Every entry is held in memory, so the
data keeps accumulating there without limit.

**Cheapest change.** Keep snapshots, meaning results that are already
worked out, and store them permanently in a database. Load the underlying
transactions only when they are needed (lazy load).

## 2. Value-dated entries in production

**Operational surface.** In day-to-day banking, value-dated entries put the
bank at risk of negative balances in many cases. They also disturb every
calculation built on a balance, such as fees and interest.

**Regulatory surface.** They create room for clarifications and complaints:
customers see different balances at different times, and the bank can end up
breaking a promise it made when it answered an authorization.

**Control before going live.** Either do not allow backdating at all, or
allow it only up to one month back and only with a second approval.

## 3. Authorization lifecycle

An authorization can end in these situations:

| Ending | What the system should do |
|---|---|
| Settled in full | The normal case. |
| Settled in part | |
| Never settled | Put an expiry date on the hold. |
| Cancelled | Settle it as zero. |
| Settlement asks for more than was authorized | Do not allow more than the authorized amount. |

## 4. What I cut and why

**Checks left out.**

- duplicate events
- unknown or unexpected values
- corrupt data

**Assumptions made in place of a rule.**

- fees are not refunded after a reversal
- no fee is defined for the dinar account
