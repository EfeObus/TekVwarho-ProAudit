# TekVwarho ProAudit - UI/UX Research Document

**Document Version:** 1.0  
**Date:** January 3, 2026  
**Research Phase:** Discovery & Definition  
**Author:** UX Research Team  

---

## Executive Summary

This document outlines the user research, design principles, and UX guidelines for TekVwarho ProAudit. Given the critical nature of tax compliance and the diverse user base across Nigeria, our design approach prioritizes **clarity, accessibility, and error prevention** above aesthetic complexity.

---

## Table of Contents

1. [Research Methodology](#1-research-methodology)
2. [User Personas](#2-user-personas)
3. [User Research Findings](#3-user-research-findings)
4. [Design Principles](#4-design-principles)
5. [Information Architecture](#5-information-architecture)
6. [Wireframe Specifications](#6-wireframe-specifications)
7. [UI Component Guidelines](#7-ui-component-guidelines)
8. [Accessibility Standards](#8-accessibility-standards)
9. [Responsive Web and Desktop Considerations](#9-responsive-web--desktop-considerations)
10. [Localization & Nigerian Context](#10-localization--nigerian-context)
11. [Usability Testing Plan](#11-usability-testing-plan)

---

## 1. Research Methodology

### 1.1 Research Objectives

1. Understand current pain points in Nigerian tax compliance workflows
2. Identify technology literacy levels across target user segments
3. Determine critical features vs. "nice-to-have" features
4. Map existing mental models for accounting/tax software

### 1.2 Research Methods (Planned)

| Method | Participants | Purpose |
|--------|--------------|---------|
| **Contextual Inquiry** | 10 SME owners | Observe current workflows |
| **User Interviews** | 20 participants | Deep-dive into pain points |
| **Survey** | 500+ respondents | Quantitative validation |
| **Competitive Analysis** | 8 products | Feature benchmarking |
| **Card Sorting** | 15 participants | Information architecture |
| **Usability Testing** | 12 participants | Prototype validation |

### 1.3 Research Timeline

```
Phase 1: Discovery (Weeks 1-3)
├── Stakeholder interviews
├── Competitive analysis
└── Initial user interviews

Phase 2: Define (Weeks 4-6)
├── Persona development
├── Journey mapping
└── Information architecture

Phase 3: Design (Weeks 7-10)
├── Wireframing
├── Prototype development
└── Usability testing

Phase 4: Iterate (Ongoing)
├── Analyze test results
├── Refine designs
└── Prepare for development
```

---

## 2. User Personas

### 2.1 Primary Persona: Chidi - SME Owner

```
┌─────────────────────────────────────────────────────────────────┐
│  PERSONA: CHIDI OKONKWO                                         │
│  "I just want to run my business without worrying about FIRS"   │
├─────────────────────────────────────────────────────────────────┤
│  Demographics:                                                  │
│  • Age: 38                                                      │
│  • Location: Lagos (Ikeja)                                      │
│  • Education: B.Sc. Business Administration                     │
│  • Business: Electronics retail, 4 employees                    │
│  • Annual Turnover: ₦45M                                        │
│  • Tech Savviness: Moderate (uses WhatsApp, mobile banking)     │
│                                                                 │
│  Goals:                                                         │
│  ✓ Stay compliant with tax laws                                 │
│  ✓ Reduce reliance on expensive accountants                     │
│  ✓ Understand his financial position at any time                │
│  ✓ Avoid penalties and audits                                   │
│                                                                 │
│  Frustrations:                                                  │
│  ✗ "Tax laws change and no one tells me"                        │
│  ✗ "I don't know if my accountant is doing things correctly"    │
│  ✗ "Excel sheets get corrupted and I lose data"                 │
│  ✗ "I can't afford QuickBooks and it doesn't work for Nigeria"  │
│                                                                 │
│  Technology Usage:                                              │
│  • Primary: Android smartphone (budget device)                  │
│  • Secondary: Windows laptop (for business)                     │
│  • Connectivity: 4G mobile data (intermittent)                  │
│  • Prefers: WhatsApp > Email > Phone calls                      │
│                                                                 │
│  Key Quote:                                                     │
│  "If your app can send me a WhatsApp when I need to pay VAT,    │
│   I will never miss a deadline again."                          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Secondary Persona: Ngozi - Internal Accountant

```
┌─────────────────────────────────────────────────────────────────┐
│  PERSONA: NGOZI ADEKUNLE                                        │
│  "I need accurate, auditable records - no cutting corners"      │
├─────────────────────────────────────────────────────────────────┤
│  Demographics:                                                  │
│  • Age: 32                                                      │
│  • Location: Abuja                                              │
│  • Education: ACA (Chartered Accountant)                        │
│  • Company: Manufacturing firm, 50 employees                    │
│  • Company Turnover: ₦350M                                      │
│  • Tech Savviness: High                                         │
│                                                                 │
│  Goals:                                                         │
│  ✓ Maintain GAAP-compliant books                                │
│  ✓ Produce reports that pass external audit                     │
│  ✓ Minimize manual data entry                                   │
│  ✓ Track multi-entity transactions                              │
│                                                                 │
│  Frustrations:                                                  │
│  ✗ "Our ERP doesn't understand Nigerian tax"                    │
│  ✗ "I spend 3 days each month on reconciliation"                │
│  ✗ "The new e-invoicing requirement is a nightmare"             │
│  ✗ "I need a proper audit trail - receipts attached to entries" │
│                                                                 │
│  Technology Usage:                                              │
│  • Primary: MacBook Pro (company-issued)                        │
│  • Software: Sage, Excel, TaxPro Max                            │
│  • Connectivity: Stable broadband                               │
│                                                                 │
│  Key Quote:                                                     │
│  "If I can get the e-invoice IRN automatically embedded in      │
│   my journal entry, that alone is worth the subscription."      │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Tertiary Persona: Uche - Tax Consultant

```
┌─────────────────────────────────────────────────────────────────┐
│  PERSONA: UCHE NNAMDI                                           │
│  "My clients need me to find savings, not just file returns"    │
├─────────────────────────────────────────────────────────────────┤
│  Demographics:                                                  │
│  • Age: 45                                                      │
│  • Location: Port Harcourt                                      │
│  • Credentials: FCA, CITN Fellow                                │
│  • Firm: Independent tax consultancy, 15 clients                │
│  • Tech Savviness: Moderate                                     │
│                                                                 │
│  Goals:                                                         │
│  ✓ Review client books efficiently                              │
│  ✓ Identify tax optimization opportunities                      │
│  ✓ Prepare compliant filings quickly                            │
│  ✓ Maintain professional reputation                             │
│                                                                 │
│  Frustrations:                                                  │
│  ✗ "Every client uses different software - or worse, paper"     │
│  ✗ "I can't trust client data without verification"             │
│  ✗ "The new Input VAT rules are complex to explain"             │
│  ✗ "I need read-only access without breaking things"            │
│                                                                 │
│  Technology Usage:                                              │
│  • Primary: Windows laptop                                      │
│  • Software: Excel (expert level), TaxPro Max                   │
│                                                                 │
│  Key Quote:                                                     │
│  "Give me an auditor login that shows everything but lets me    │
│   add notes without changing the books."                        │
└─────────────────────────────────────────────────────────────────┘
```

### 2.4 Government Stakeholder Persona: DG - NRS Official

```
┌─────────────────────────────────────────────────────────────────┐
│  PERSONA: DR. ADEBAYO JOHNSON                                   │
│  "We want technology that increases compliance, not barriers"   │
├─────────────────────────────────────────────────────────────────┤
│  Demographics:                                                  │
│  • Role: Director, Taxpayer Services, NRS                       │
│  • Focus: E-Invoicing adoption, SME compliance                  │
│                                                                 │
│  Goals:                                                         │
│  ✓ Increase voluntary tax compliance                            │
│  ✓ Reduce manual processing burden                              │
│  ✓ Improve data quality from taxpayers                          │
│  ✓ Support SME formalization                                    │
│                                                                 │
│  Expectations from Partner Software:                            │
│  ✓ 100% compliant with NRS e-invoicing spec                     │
│  ✓ Data security and privacy assurance                          │
│  ✓ Real-time reporting capabilities                             │
│  ✓ Taxpayer education integration                               │
│                                                                 │
│  Key Quote:                                                     │
│  "If your software makes it easy to be compliant, you're        │
│   doing our job for us - and we'll support you."                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. User Research Findings

### 3.1 Pain Point Analysis (Preliminary)

| Pain Point | Severity | Frequency | Design Implication |
|------------|----------|-----------|-------------------|
| Complex tax rules | Critical | Universal | Auto-calculate; explain in plain language |
| Fear of penalties | High | Very Common | Clear deadline alerts; confirmation of compliance |
| Distrust of data accuracy | High | Common | Visible audit trails; reconciliation status |
| Poor connectivity | Medium | Common | Offline mode; sync when connected |
| Limited accounting knowledge | Medium | Common | Guided flows; in-context help |
| Time constraints | High | Universal | Quick entry options; batch processing |

### 3.2 Current Workflow Analysis

```
TYPICAL NIGERIAN SME TAX WORKFLOW (As-Is)

                 Excel/Paper
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    ▼                ▼                ▼
Sales Records   Expense Records   Bank Statements
    │                │                │
    └────────────────┼────────────────┘
                     │
                     ▼
              External Accountant
              (Monthly Visit)
                     │
                     ▼
              Tally/Manual Books
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    ▼                ▼                ▼
VAT Filing      PAYE Remittance   Annual Returns
(Late/Errors)   (Manual Calc)     (Rush Job)
```

### 3.3 Opportunity Areas

1. **Automation Hunger:** Users desperately want automation but distrust it; need transparency
2. **Compliance Anxiety:** High stress around tax deadlines; opportunity for proactive alerts
3. **Trust Gap:** Users need to verify system calculations; show work, not just results
4. **Education Need:** Users don't understand tax benefits (e.g., Input VAT recovery)
5. **Mobility:** Many transactions happen outside office; mobile capture is essential

---

## 4. Design Principles

### 4.1 Core Principles

```
┌─────────────────────────────────────────────────────────────────┐
│  TEKVWARHO PROAUDIT DESIGN PRINCIPLES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. CLARITY OVER CLEVERNESS                                     │
│     • Plain language always                                     │
│     • No jargon without explanation                             │
│     • Show calculations, not just results                       │
│                                                                 │
│  2. ERROR PREVENTION, NOT JUST CORRECTION                       │
│     • Validate inputs before submission                         │
│     • Warn before irreversible actions                          │
│     • Auto-save everything                                      │
│                                                                 │
│  3. PROGRESSIVE DISCLOSURE                                      │
│     • Show essentials first                                     │
│     • Reveal complexity on demand                               │
│     • Default to the 80% use case                               │
│                                                                 │
│  4. TRANSPARENCY BUILDS TRUST                                   │
│     • Show system status clearly                                │
│     • Explain why actions are needed                            │
│     • Provide audit trails for everything                       │
│                                                                 │
│  5. NIGERIA-FIRST DESIGN                                        │
│     • Naira (₦) always primary                                  │
│     • Date format: DD/MM/YYYY                                   │
│     • Designed for intermittent connectivity                    │
│     • Works on budget Android devices                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Visual Design Direction

| Aspect | Approach | Rationale |
|--------|----------|-----------|
| **Color Palette** | Nigerian Green (#008751) & White | National sovereignty colors, trust, professional |
| **Typography** | Inter (Sans-serif), clear hierarchy | Readability on all devices |
| **Density** | Moderate, generous whitespace | Reduce overwhelm, aid focus |
| **Icons** | Minimal, purposeful | Reduce cognitive load |
| **Charts** | Simple bar/line, avoid 3D | Quick comprehension |

### 4.3 Color System

```
PRIMARY PALETTE - Nigerian National Colors
──────────────────────────────────────────
Nigerian Green:  #008751 (Primary brand, actions, headers, success)
White:           #FFFFFF (Primary background, contrast)
Dark Green:      #006B41 (Hover states, emphasis)

SECONDARY PALETTE
────────────────
Trust Blue:      #1E40AF (Links, informational elements)
Alert Red:       #DC2626 (Errors, overdue items)
Warning Amber:   #F59E0B (Warnings, attention needed)
Neutral Gray:    #6B7280 (Secondary text, borders)

BACKGROUND SYSTEM
────────────────
Pure White:      #FFFFFF (Primary background - clean, professional)
Off White:       #F8FAF8 (Card backgrounds - subtle green tint)
Light Gray:      #F3F4F6 (Alternate backgrounds)
Divider:         #E5E7EB (Lines, borders)

BRAND APPLICATION
────────────────
The green and white color scheme reflects Nigeria's national flag,
conveying trust, patriotism, and alignment with national institutions.
Green is used for primary actions, navigation, and key UI elements.
White provides a clean, professional backdrop for financial data.

ACCESSIBILITY NOTES
────────────────
All text meets WCAG AA contrast ratios (4.5:1 minimum)
Color is never the only indicator of status (icons/text accompany)
High contrast mode available for accessibility compliance
```

---

## 5. Information Architecture

### 5.1 Navigation Structure

```
TEKVWARHO PROAUDIT - NAVIGATION MAP

┌──────────────────────────────────────────────────────────────────┐
│                        GLOBAL HEADER                              │
│  [Logo] [Entity Selector ▼] [Search] [Alerts 🔔] [Profile ▼]     │
└──────────────────────────────────────────────────────────────────┘

┌──────────────┬───────────────────────────────────────────────────┐
│ SIDEBAR      │                MAIN CONTENT AREA                  │
│──────────────│───────────────────────────────────────────────────│
│ Dashboard    │                                                   │
│              │    [Context-dependent content]                    │
│ Income       │                                                   │
│   └─ Invoices│                                                   │
│   └─ Receipts│                                                   │
│              │                                                   │
│ Expenses     │                                                   │
│   └─ Record  │                                                   │
│   └─ OCR Scan│                                                   │
│              │                                                   │
│ Inventory    │                                                   │
│   └─ Stock   │                                                   │
│   └─ Write-offs                                                  │
│              │                                                   │
│ Vendors      │                                                   │
│              │                                                   │
│ Payroll      │                                                   │
│   └─ Employees                                                   │
│   └─ PAYE Calc                                                   │
│              │                                                   │
│ Banking      │                                                   │
│   └─ Accounts│                                                   │
│   └─ Reconcile                                                   │
│              │                                                   │
│ Compliance   │                                                   │
│   └─ VAT     │                                                   │
│   └─ CIT     │                                                   │
│   └─ WHT     │                                                   │
│   └─ E-Invoices                                                  │
│              │                                                   │
│ Reports      │                                                   │
│              │                                                   │
│ Settings     │                                                   │
└──────────────┴───────────────────────────────────────────────────┘
```

### 5.2 User Flows

#### Flow 1: Record Expense (Mobile)

```
START → [+] FAB → Select Type → Expense

           ┌────────────────────┐
           │   Quick Add        │
           │ ┌───────────────┐  │
           │ │ 📷 Scan Receipt│ │◄─── Primary CTA
           │ └───────────────┘  │
           │                    │
           │ OR                 │
           │                    │
           │ ┌───────────────┐  │
           │ │ ✏️ Manual Entry │ │
           │ └───────────────┘  │
           └────────────────────┘
                    │
                    ▼
          ┌─────────────────────┐
          │ OCR Processing...   │
          │ [████████░░] 80%    │
          └─────────────────────┘
                    │
                    ▼
          ┌─────────────────────┐
          │ Review Extracted    │
          │                     │
          │ Date: [01/03/2026]  │
          │ Amount: [₦45,000]   │
          │ Vendor: [MTN NG]    │
          │ Category: [Telecom] │
          │                     │
          │ Tax Deductible?     │
          │ [✓] WREN Compliant  │
          │                     │
          │ [Save]   [Edit]     │
          └─────────────────────┘
                    │
                    ▼
          ┌─────────────────────┐
          │ ✓ Expense Saved     │
          │   ₦45,000           │
          │                     │
          │ [Add Another]       │
          │ [View Expenses]     │
          └─────────────────────┘
```

#### Flow 2: Create & Submit E-Invoice

```
Invoice Creation Flow
───────────────────────

STEP 1: Customer Details
┌────────────────────────────┐
│ Customer                   │
│ [Search or Add New...]     │
│                            │
│ Name: Dangote Industries   │
│ TIN: [12345678-0001] ✓     │
│ Address: Lekki, Lagos      │
└────────────────────────────┘
         │
         ▼
STEP 2: Line Items
┌────────────────────────────┐
│ Items                      │
│ ┌────┬─────────┬────────┐  │
│ │Qty │ Item    │ Amount │  │
│ ├────┼─────────┼────────┤  │
│ │ 10 │ Widget A│ ₦50,000│  │
│ │  5 │ Widget B│ ₦25,000│  │
│ └────┴─────────┴────────┘  │
│ [+ Add Item]               │
│                            │
│ Subtotal:      ₦75,000     │
│ VAT (7.5%):    ₦5,625      │
│ ─────────────────────────  │
│ TOTAL:         ₦80,625     │
└────────────────────────────┘
         │
         ▼
STEP 3: Review & Submit
┌────────────────────────────┐
│ Invoice Preview            │
│ ┌────────────────────────┐ │
│ │ [Invoice Visual]       │ │
│ └────────────────────────┘ │
│                            │
│  Submitting to NRS will: │
│ • Generate IRN             │
│ • Add QR Code              │
│ • Lock invoice from edits  │
│                            │
│ [Save Draft] [Submit →]    │
└────────────────────────────┘
         │
         ▼
STEP 4: NRS Confirmation
┌────────────────────────────┐
│ ✓ Invoice Submitted to NRS │
│                            │
│ IRN: NRS-2026-0001234567   │
│ [QR CODE]                  │
│                            │
│ [Download PDF]             │
│ [Email to Customer]        │
│ [WhatsApp Share]           │
└────────────────────────────┘
```

---

## 6. Wireframe Specifications

### 6.1 Dashboard Wireframe

```
┌──────────────────────────────────────────────────────────────────────┐
│ DASHBOARD                                                    Jan 2026 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ ┌─────────────────────────────────────────────────────────────────┐  │
│ │ COMPLIANCE ALERTS                                               │  │
│ │ ────────────────────────────────────────────────────────────────│  │
│ │ [!] VAT Filing Due: 5 days remaining                    [File →]│  │
│ │ [!] 3 Invoices pending NRS submission               [Submit All]│  │
│ └─────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │
│ │ REVENUE     │ │ EXPENSES    │ │ NET INCOME  │ │ VAT BALANCE │     │
│ │ ₦4.2M ↑12%  │ │ ₦2.8M ↑5%   │ │ ₦1.4M ↑23%  │ │ ₦315K       │     │
│ │ This Month  │ │ This Month  │ │ This Month  │ │ Due to NRS  │     │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │
│                                                                      │
│ ┌────────────────────────────────┐ ┌────────────────────────────┐   │
│ │ REVENUE VS EXPENSES            │ │ UPCOMING TAX DEADLINES     │   │
│ │ ┌────────────────────────────┐ │ │ ─────────────────────────  │   │
│ │ │                            │ │ │ 21 Jan │ VAT Filing     🔴│   │
│ │ │ [Line Chart: 6 months]     │ │ │ 31 Jan │ PAYE Remittance│   │
│ │ │                            │ │ │ 15 Feb │ WHT Filing     │   │
│ │ │                            │ │ │ 31 Mar │ Q1 Returns     │   │
│ │ └────────────────────────────┘ │ │                            │   │
│ └────────────────────────────────┘ └────────────────────────────┘   │
│                                                                      │
│ ┌────────────────────────────────┐ ┌────────────────────────────┐   │
│ │ RECENT TRANSACTIONS            │ │ LOW STOCK ALERTS           │   │
│ │ ─────────────────────────────  │ │ ─────────────────────────  │   │
│ │ Today  Invoice #1234  +₦85K    │ │ Widget A │ 5 units left    │   │
│ │ Today  Expense (MTN) -₦12K     │ │ Widget B │ 3 units left    │   │
│ │ Y'day  Payment Recd  +₦120K    │ │                            │   │
│ │ Y'day  Salary        -₦450K    │ │ [View Inventory →]         │   │
│ │ [View All →]                   │ │                            │   │
│ └────────────────────────────────┘ └────────────────────────────┘   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 Mobile Dashboard Wireframe

```
┌─────────────────────────┐
│ ☰  TekVwarho    🔔 2    │
├─────────────────────────┤
│                         │
│ Good morning, Chidi     │
│ Chidi Electronics Ltd   │
│                         │
│ ┌───────────────────┐   │
│ │  VAT DUE: 5 DAYS │   │
│ │ [File Now →]      │   │
│ └───────────────────┘   │
│                         │
│ ┌─────────┐ ┌─────────┐ │
│ │ Revenue │ │Expenses │ │
│ │ ₦4.2M   │ │ ₦2.8M   │ │
│ │ ↑ 12%   │ │ ↑ 5%    │ │
│ └─────────┘ └─────────┘ │
│                         │
│ Quick Actions           │
│ ┌──────┐ ┌──────┐       │
│ │ 📷   │ │ 📄   │       │
│ │ Scan │ │ Invoice│      │
│ └──────┘ └──────┘       │
│ ┌──────┐ ┌──────┐       │
│ │    │ │    │       │
│ │Income│ │Reports│       │
│ └──────┘ └──────┘       │
│                         │
│ Recent Activity         │
│ ├─ Invoice #1234  +₦85K │
│ ├─ MTN Expense   -₦12K  │
│ └─ Payment Recd +₦120K  │
│                         │
│     ────────────────    │
│         [+]             │◄── Floating Action Button
└─────────────────────────┘
```

---

## 7. UI Component Guidelines

### 7.1 Button Hierarchy

| Type | Usage | Style |
|------|-------|-------|
| **Primary** | Main actions (Save, Submit, Create) | Solid green background, white text |
| **Secondary** | Alternative actions (Cancel, Back) | Outlined, green border |
| **Tertiary** | Minor actions (Edit, View Details) | Text only, no border |
| **Destructive** | Delete, Remove | Red background or text |
| **Ghost** | Navigation, Less important | Light gray text |

### 7.2 Form Design

```
FORM FIELD ANATOMY
────────────────────────────────────────
┌────────────────────────────────────┐
│ Label*                    ⓘ Tooltip│  ← Help icon for complex fields
├────────────────────────────────────┤
│ Placeholder text...               │  ← Input field
├────────────────────────────────────┤
│ Helper text or validation message │  ← Context/error
└────────────────────────────────────┘

VALIDATION STATES
─────────────────
• Default: Gray border
• Focus: Green border, subtle shadow
• Valid: Green border, ✓ icon
• Error: Red border, error message below
• Disabled: Gray background, muted text
```

### 7.3 Data Tables

```
TABLE DESIGN SPECIFICATION
────────────────────────────────────────────────────────────────
┌────────────────────────────────────────────────────────────┐
│ INVOICES                          [Export ▼] [+ New]       │
├────────────────────────────────────────────────────────────┤
│ [Search invoices...]           Filter: [All ▼] [Date ▼]   │
├────────────────────────────────────────────────────────────┤
│ □ │ Invoice #   │ Customer      │ Amount   │ Status │ ⋮   │
├───┼─────────────┼───────────────┼──────────┼────────┼─────┤
│ □ │ INV-2026-01 │ Dangote Ind.  │ ₦850,000 │ ✓ Paid │ ⋮   │
│ □ │ INV-2026-02 │ MTN Nigeria   │ ₦125,000 │ ⏳ Pending│ ⋮ │
│ □ │ INV-2026-03 │ Shell Nigeria │ ₦2.4M    │  Overdue│ ⋮ │
├────────────────────────────────────────────────────────────┤
│ ◀ 1 2 3 ... 15 ▶                    Showing 1-10 of 150   │
└────────────────────────────────────────────────────────────┘

STATUS BADGES
─────────────
✓ Paid/Complete: Green badge
⏳ Pending: Yellow badge
 Overdue/Alert: Red badge
📤 Submitted: Blue badge
```

### 7.4 Currency Display

```
NAIRA FORMATTING RULES
──────────────────────
• Always use ₦ symbol (not NGN)
• Thousands separator: comma
• No decimal for whole amounts
• 2 decimals when kobo present

Examples:
✓ ₦1,250,000
✓ ₦45,000.50
✗ NGN 1250000
✗ N 1,250,000

LARGE NUMBERS
─────────────
• ₦1.2M for millions
• ₦850K for thousands
• Full number on hover/tap
```

---

## 8. Accessibility Standards

### 8.1 WCAG 2.1 AA Compliance

| Criterion | Requirement | Implementation |
|-----------|-------------|----------------|
| **1.4.3 Contrast** | 4.5:1 for normal text | All text colors verified |
| **1.4.11 Non-text Contrast** | 3:1 for UI components | Buttons, inputs, icons |
| **2.1.1 Keyboard** | All functions keyboard-accessible | Tab order, focus indicators |
| **2.4.7 Focus Visible** | Clear focus indicators | 2px green outline |
| **1.1.1 Text Alternatives** | Alt text for images | All icons have labels |

### 8.2 Nigerian Context Accessibility

| Consideration | Approach |
|---------------|----------|
| **Low-bandwidth tolerance** | Lazy loading, compressed images, minimal animations |
| **Budget devices** | Target 2GB RAM, 720p screens |
| **Screen readers** | Compatible with TalkBack (Android) |
| **Age-related vision** | Minimum 16px font, high contrast option |

---

## 9. Responsive Web & Desktop Considerations

Note: TekVwarho ProAudit is a web-first application. No mobile native app is 
planned. Future development will include desktop applications (Windows/macOS).
The web application is fully responsive and optimized for use on mobile devices
through the browser.

### 9.1 Responsive Breakpoints

| Breakpoint | Device Type | Layout |
|------------|-------------|--------|
| **< 640px** | Mobile Browser (Portrait) | Single column, bottom nav |
| **640-1024px** | Tablet Browser | Two column, sidebar collapsible |
| **> 1024px** | Desktop Browser | Full sidebar, multi-column |
| **Desktop App** | Windows/macOS (Future) | Native experience, offline-first |

### 9.2 Touch Targets (For Mobile Browser)

- Minimum touch target: **44x44px**
- Spacing between targets: **8px minimum**
- FAB size: **56px diameter**

### 9.3 Offline Functionality (Desktop App - Future)

| Feature | Offline Capability |
|---------|-------------------|
| View dashboard | Cached data |
| Record expense | Queued for sync |
| Create invoice | Draft mode, submit when online |
| OCR scan | Basic capture, process when online |
| Submit e-invoice | Requires connectivity |
| Bank sync | Requires connectivity |

---

## 10. Localization & Nigerian Context

### 10.1 Language Support

| Priority | Language | Coverage |
|----------|----------|----------|
| P0 | English (Nigerian) | 100% |
| P1 | Pidgin English | Key UI elements, tooltips |
| P2 | Yoruba, Igbo, Hausa | Future consideration |

### 10.2 Nigerian-Specific UX Elements

| Element | Nigerian Adaptation |
|---------|---------------------|
| **Currency** | ₦ always, no foreign currency default |
| **Date** | DD/MM/YYYY format |
| **Phone** | +234 auto-prefix, 11-digit validation |
| **TIN** | Format: 12345678-0001 (with hyphen) |
| **Address** | State-LGA dropdown hierarchy |
| **Bank** | Nigerian bank list with sort codes |

### 10.3 Cultural Considerations

- **Trust indicators:** Show NRS certification badge prominently
- **Government association:** Use official green color palette carefully
- **Business etiquette:** Formal language in official documents
- **Religious sensitivity:** No imagery that conflicts with major religions

---

## 11. Usability Testing Plan

### 11.1 Test Objectives

1. Validate navigation intuitiveness for non-technical users
2. Measure time-to-complete for core tasks
3. Identify pain points in e-invoicing flow
4. Assess comprehension of tax calculations

### 11.2 Test Tasks

| Task | Success Criteria | Time Target |
|------|------------------|-------------|
| Record an expense using OCR | Successfully saved with correct amount | < 60 seconds |
| Create and submit an invoice | Invoice submitted, IRN received | < 3 minutes |
| Find VAT amount owed | Correct number identified | < 30 seconds |
| Run a P&L report | PDF generated | < 2 minutes |
| Add a new employee to payroll | Employee saved with correct PAYE calc | < 5 minutes |

### 11.3 Test Participant Criteria

- **Segment A (8 participants):** SME owners with < 2 years accounting software experience
- **Segment B (4 participants):** Professional accountants
- **Device distribution:** 60% Android mobile, 30% iOS, 10% Desktop

### 11.4 Testing Schedule

| Phase | Timing | Purpose |
|-------|--------|---------|
| **Alpha Testing** | Week 8 | Internal team, catch critical issues |
| **Beta Testing** | Week 10 | 20 external users, real-world scenarios |
| **Launch Readiness** | Week 12 | Final validation before MVP |

---

## 12. Recommendations Summary

### 12.1 Immediate Design Priorities

1. **Dashboard:** Compliance alerts must be unmissable
2. **Mobile OCR:** Fastest path to value for SME owners
3. **E-Invoice Flow:** Must be bulletproof with clear error handling
4. **Offline Mode:** Essential for Nigerian connectivity reality

### 12.2 Design Debt to Avoid

- Do not over-engineer the first version
- Avoid complex multi-step wizards where simpler flows work
- Do not add features that require stable internet
- Avoid animations that slow down budget devices

### 12.3 Success Metrics (UX)

| Metric | Target |
|--------|--------|
| Task Success Rate | > 90% |
| System Usability Scale (SUS) | > 75 |
| Time to First Invoice | < 10 minutes |
| User Satisfaction (NPS) | > 60 |

---

## 13. Enhanced UX Recommendations (NTA 2025 Alignment)

### 13.1 NRS "Clearance" Status Indicators

Implement a clear visual status progression for all e-invoices:

```
E-INVOICE STATUS FLOW
---------------------

[Draft] -----> [Validated] -----> [Final]
   |              |                  |
   |              |                  |
 Gray         Blue + IRN        Green + Locked
 Editable      Received         72hr Closed

Visual Implementation:

+--------------------------------------------------+
| Invoice INV-2026-001234                          |
+--------------------------------------------------+
| Status: [Validated - IRN Received]               |
|         NRS-2026-AB123456789                     |
|                                                   |
| Timeline:                                         |
| [x] Draft Created        - 03 Jan 2026 09:15    |
| [x] Submitted to NRS     - 03 Jan 2026 09:18    |
| [x] IRN Received         - 03 Jan 2026 09:18    |
| [ ] 72hr Window Closes   - 06 Jan 2026 09:18    |
|                                                   |
| WARNING: Invoice can be amended until 06 Jan.    |
| After 72hrs, invoice becomes FINAL.              |
+--------------------------------------------------+
```

**Key Design Requirements:**
- Clear color coding: Gray (draft), Blue (validated), Green (final)
- Countdown timer showing time remaining in 72-hour amendment window
- Prominent display of IRN once received
- Lock icon appears when invoice becomes final
- Amendment history visible for audit purposes

### 13.2 Tax-Logic Explainer Info-Bubbles

Every tax calculation should include an information bubble explaining the logic:

```
TAX EXPLAINER PATTERN
---------------------

+--------------------------------------------------+
| VAT Calculation                            [?]   |
+--------------------------------------------------+
| Output VAT (Sales):           N75,000           |
| Less: Input VAT (Expenses):   N22,500           |
| ----------------------------------------------- |
| Net VAT Payable:              N52,500           |
+--------------------------------------------------+

[?] Info-bubble content (on click/hover):
+--------------------------------------------------+
| HOW THIS IS CALCULATED                           |
| ------------------------------------------------ |
| Under NTA 2025, VAT is charged at 7.5% on       |
| taxable supplies. You can recover VAT paid on   |
| business expenses (Input VAT) against VAT       |
| collected on sales (Output VAT).                |
|                                                  |
| Your calculation:                                |
| - Total Sales: N1,000,000 x 7.5% = N75,000      |
| - Eligible Expenses: N300,000 x 7.5% = N22,500  |
| - Net Payable: N75,000 - N22,500 = N52,500      |
|                                                  |
| Note: 3 expenses (N45,000) were not eligible    |
| for Input VAT recovery (non-WREN compliant).    |
|                                                  |
| [Learn More About VAT]                          |
+--------------------------------------------------+
```

**Implementation Guidelines:**
- Use consistent [?] icon placement (top-right of calculation cards)
- Explain in plain Nigerian English, avoid technical jargon
- Show actual numbers from user's data, not generic examples
- Link to relevant sections of compliance documentation
- Make explainers dismissible but easily accessible

### 13.3 WREN Eligibility Toggle

Simple "Business Use?" checkbox on every expense entry:

```
EXPENSE ENTRY WITH WREN TOGGLE
------------------------------

+--------------------------------------------------+
| New Expense                                      |
+--------------------------------------------------+
| Date:        [03/01/2026    ]                   |
| Amount:      [N 45,000      ]                   |
| Vendor:      [MTN Nigeria   ] [Verify TIN]      |
| Category:    [Telecommunications   v]           |
| Description: [Office internet subscription    ] |
|                                                  |
| +----------------------------------------------+|
| | [x] Business Use                        [?]  ||
| |     This expense is wholly and exclusively   ||
| |     for business purposes                    ||
| +----------------------------------------------+|
|                                                  |
| WREN Status: [ELIGIBLE] - Input VAT recoverable |
|                                                  |
| [Cancel]                         [Save Expense] |
+--------------------------------------------------+

[?] Info-bubble content:
+--------------------------------------------------+
| WREN COMPLIANCE                                  |
| ------------------------------------------------ |
| Under the Wholly, Reasonably, Exclusively, and  |
| Necessarily (WREN) test, expenses must be       |
| incurred wholly and exclusively for business    |
| purposes to qualify for tax deduction and       |
| Input VAT recovery.                             |
|                                                  |
| Examples of ELIGIBLE expenses:                  |
| - Office rent and utilities                     |
| - Business travel and accommodation             |
| - Professional services (legal, accounting)     |
| - Stock and inventory purchases                 |
|                                                  |
| Examples of NON-ELIGIBLE expenses:              |
| - Personal phone bills                          |
| - Entertainment not related to business         |
| - Fines and penalties                           |
|                                                  |
| [Read WREN Guidelines]                          |
+--------------------------------------------------+
```

**Design Specifications:**
- Checkbox is checked by default for business accounts
- Unchecking triggers a confirmation: "This expense will not be eligible for Input VAT recovery"
- Category auto-suggests WREN status based on expense type
- Clear visual indicator of WREN status (green badge = eligible, gray = not eligible)
- Tooltip explains the financial impact of the selection

### 13.4 72-Hour Dispute Monitor

Notification tray component for tracking e-invoice amendment windows:

```
DISPUTE MONITOR COMPONENT
-------------------------

+--------------------------------------------------+
| 72-HOUR AMENDMENT WINDOWS            [Settings] |
+--------------------------------------------------+
| Closing Soon:                                    |
|                                                  |
| [!] INV-2026-001234  - Dangote Industries       |
|     Closes in: 2 hours 15 minutes               |
|     [Review] [Amend]                            |
|                                                  |
| [!] INV-2026-001233  - MTN Nigeria              |
|     Closes in: 18 hours 42 minutes              |
|     [Review] [Amend]                            |
|                                                  |
+--------------------------------------------------+
| Recently Finalized:                             |
|                                                  |
| [OK] INV-2026-001232  - Shell Nigeria           |
|      Finalized: 02 Jan 2026 14:30              |
|                                                  |
+--------------------------------------------------+
| [View All E-Invoices]                           |
+--------------------------------------------------+
```

**Notification Rules:**
- Push notification at 24 hours remaining
- Push notification at 4 hours remaining  
- Push notification at 1 hour remaining
- Dashboard alert for all invoices under 24 hours
- Color coding: Red (< 4hrs), Amber (< 24hrs), Blue (active)

---

## Appendix A: Competitive Analysis Summary

| Product | Strengths | Weaknesses | Opportunity |
|---------|-----------|------------|-------------|
| **QuickBooks** | Feature-rich, trusted | Not Nigeria-compliant, expensive | Beat on compliance |
| **Sage** | Enterprise-grade | Complex, no e-invoicing | Simpler UX |
| **Wave** | Free, easy | No Nigerian tax | Full Nigeria support |
| **Local Apps** | Naira-first | Poor UX, incomplete | Superior design |

---

## Appendix B: Design System Tokens (Preview)

```css
/* Color Tokens */
--color-primary: #008751;
--color-primary-dark: #006B41;
--color-secondary: #1E40AF;
--color-error: #DC2626;
--color-warning: #F59E0B;
--color-success: #10B981;

/* Typography Tokens */
--font-family: 'Inter', system-ui, sans-serif;
--font-size-xs: 12px;
--font-size-sm: 14px;
--font-size-base: 16px;
--font-size-lg: 18px;
--font-size-xl: 20px;
--font-size-2xl: 24px;
--font-size-3xl: 32px;

/* Spacing Tokens */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;

/* Border Radius */
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-full: 9999px;
```

---

*Document prepared by UX Research Team | TekVwarho ProAudit*
