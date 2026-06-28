# End-to-End Flow

## Purpose

This document describes the end-to-end operational and accounting flow for the Property Management module after adapting it for Yemen, where transactions may be handled in both `YER` and `SAR`.

The goal is to keep:
- leasing operations consistent
- accounting entries correct
- currency handling explicit
- journals and accounts configurable per property

## Scope

This flow covers:
- property setup
- unit setup
- tenant and owner onboarding
- lease creation and activation
- payment schedule generation
- rent collection
- security deposit handling
- refund handling
- invoice generation
- journal entry creation
- currency conversion and reconciliation

## Core Currency Model

- Company base currency: usually `YER`
- Contract currency: `YER` or `SAR`
- Payment currency: same as contract currency by default, but can differ if configured
- Company amount: converted value in company currency for accounting

The system must always store:
- transaction amount in the transaction currency
- equivalent amount in company currency
- exchange rate context via the Odoo currency conversion engine

## Master Data Setup

### 1. Property Setup

Each property should be configured with:
- rent journal
- deposit journal
- maintenance journal
- receivable account
- rent income account
- service income account
- deposit liability account
- advance liability account
- maintenance expense account
- cash/clearing account

This configuration is stored on the property record so every lease under that property can inherit the accounting setup.

### 2. Unit Setup

Each unit should define:
- property
- owner
- current status
- standard rent
- standard deposit
- market value

### 3. Tenant and Owner Setup

Each tenant and owner should have:
- linked contact
- unique code
- phone and email
- identity documents when required

## Lease Lifecycle

### 1. Draft Lease

The lease is created in draft with:
- property
- unit
- tenant
- start and end dates
- rent amount
- currency
- payment frequency
- deposit months
- escalation and late fee rules

At this stage:
- no accounting entry is posted
- payment schedule may be generated later

### 2. Review

The lease may be sent for review for internal approval.

### 3. Activation

When the lease is activated:
- the unit becomes occupied
- the active tenant and lease are linked to the unit
- payment schedule is generated if it does not exist
- the security deposit is created if applicable
- the lease state becomes active

If a deposit is required:
- a deposit record is created
- a payment record may be generated for deposit capture
- a journal entry is created through the deposit flow

## Payment Schedule Flow

### 1. Schedule Generation

The system generates schedule lines using:
- lease start date
- lease end date
- rent frequency
- escalation percentage if enabled

Each schedule line contains:
- due date
- amount
- paid amount
- remaining amount
- currency
- state

### 2. Overdue Detection

A scheduled cron job marks due items as overdue when:
- due date is in the past
- state is pending or partial

### 3. Invoice Generation

For a schedule line, the system can create an invoice:
- customer invoice is created in the contract currency
- sale journal is used
- income account is taken from the property configuration

The invoice should be used when the operational process requires formal billing before collection.

## Rent Payment Flow

### 1. Payment Registration

When rent is received:
- payment record is created
- schedule line is linked when applicable
- payment currency is set from the lease currency unless explicitly overridden
- received amount is captured

### 2. Confirmation

The payment may be confirmed before posting.

### 3. Posting

When payment is marked as paid:
- transaction is converted to company currency
- a journal entry is created
- the liquidity account is debited
- the counterpart account is credited

Typical rent posting:
- debit: cash/bank/clearing
- credit: receivable or rent income depending on the process design

If the payment is tied to an invoice:
- receivable lines are reconciled

If the payment is tied to a schedule line:
- schedule paid amount is updated
- schedule state becomes partial or paid

### 4. Currency Handling

If the payment currency differs from the company currency:
- amount is converted using Odoo currency conversion
- company amount is stored separately
- the journal entry is posted in company currency with transaction currency context

## Security Deposit Flow

### 1. Deposit Creation

On lease activation, if a deposit is required:
- deposit record is created
- deposit is linked to lease, tenant, unit, and property
- deposit currency follows the lease currency

### 2. Deposit Receipt

Deposit receipt posting creates:
- debit to cash/clearing
- credit to deposit liability

This keeps the deposit on the liability side until it is refunded or forfeited.

### 3. Deposit Refund

When the deposit is refunded:
- a refund payment is created
- a reversal journal entry is posted
- deposit state changes to refunded or partial refunded

If deductions apply:
- only the refundable amount is returned
- the deduction remains available for reporting and settlement

## Refund Flow

Refunds should never be handled only as a status change.

Correct refund handling:
- create a refund journal entry
- reverse the original posting
- update the payment state to refunded
- preserve the original transaction trail

## Maintenance Flow

Maintenance requests should remain operational and financial:
- request creation
- approval
- completion
- cost accumulation

When maintenance is billed or settled:
- costs go to maintenance expense
- vendor bill or internal journal entry may be created depending on the workflow

## Accounting Rules

### Rent

- debit liquidity or receivable
- credit rent income

### Deposit

- debit liquidity
- credit deposit liability

### Advance Payment

- debit liquidity
- credit advance liability

### Service Charge

- debit liquidity or receivable
- credit service income

### Maintenance Cost

- debit maintenance expense
- credit payable, cash, or clearing depending on the source

## Journal and Account Expectations

The module should be configured with clear account mapping per property:
- rent income
- service income
- receivable
- deposit liability
- advance liability
- maintenance expense
- cash/clearing

This avoids hardcoding and makes the module practical for different landlords and property types.

## Multi-Currency Expectations

Supported scenarios:
- contract in `YER`, collection in `YER`
- contract in `SAR`, collection in `SAR`
- contract in `SAR`, accounting in `YER`
- mixed operations where the property base currency differs from the transaction currency

The system should always preserve:
- original transaction currency
- company currency equivalent
- posted accounting entry

## User Roles

Typical roles:
- Admin
- Property Manager
- Accountant
- Maintenance Staff
- Reception
- Auditor

Suggested access pattern:
- managers manage operations
- accountants post and reconcile entries
- auditors read-only access

## Validation Rules

The system should block or warn when:
- lease is missing currency
- property missing journal/account configuration
- amount is zero or negative
- start date is after end date
- deposit or payment lacks a valid property/lease link
- currency conversion is not available and no fallback is defined

## Recommended Deployment Checklist

Before go-live:
- verify company currency
- define exchange handling policy for `YER` and `SAR`
- configure property journals and accounts
- verify invoice tax treatment if needed
- test rent receipt, deposit receipt, and refund flows
- test reports in Arabic and English
- test reconciliation against posted entries

## Operational Outcome

After this setup, the module supports:
- practical leasing operations in Yemen
- dual-currency workflows
- proper accounting traceability
- controlled deposits and refunds
- clearer owner statements and tenant balances

