# الإطار النظري — وحدة تنفيذ المقاولات

## Architecture Conceptuelle d'un ERP de Gestion de Projets de Construction

---

## 1. INTRODUCTION — Philosophy & Domain Model

### 1.1 Objectif du Module

Le module `construction_execution` est un **système intégré de gestion de cycle de vie de projet de construction** (Construction Project Lifecycle Management) construit sur Odoo 16. Il couvre :

- **Phase commerciale** : Devis, conversion CRM → Projet
- **Phase contractuelle** : Métré (BOQ), Budget, Variations
- **Phase exécution** : Approvisionnements, Avancement physique, IPC
- **Phase financière** : Facturation, Coûts, Trésorerie, Earned Value Management (EVM)

### 1.2 Principes Architecturaux

| Principe | Description |
|---|---|
| **Model prefix** | `construction.*` sans underscore (`construction.project`, `construction.boq.item`) |
| **Sécurité hiérarchique** | 11 groupes chaînés : auditor → admin (héritage `base.group_system`) |
| **Stored computed fields** | `store=True` sur les champs critiques de performance (`progress_percent`, `total_amount`, `amount`) |
| **Multi-company** | `_check_company_auto = True` sur tous les modèles |
| **Raw SQL view** | Dashboard = vue SQL avec `_auto = False` et méthode `init()` |
| **Bridge pattern** | Les ponts vers les modules Odoo core se font par actions/ boutons, pas stored fields |

### 1.3 Diagramme de Classes (Relationnel)

```
┌─────────────────────────────────────────────────────────────────────┐
│  construction.project                             (Modèle Racine)  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 1↑  *↓                                                     │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ → construction.boq             → construction.budget        │  │
│  │ → construction.boq.item        → construction.budget.line   │  │
│  │ → construction.boq.section                                  │  │
│  │ → construction.resource        → construction.rate.analysis │  │
│  │ → construction.variation       → construction.progress      │  │
│  │ → construction.ipc             → construction.cost.entry    │  │
│  │ → construction.cashflow        → construction.forecast      │  │
│  │ → construction.material.request → construction.material.plan│  │
│  │ → construction.dashboard       (vue SQL, readonly)          │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. MODÈLE CENTRAL — construction.project

### 2.1 Cycle de Vie

```
Tender ──▶ Awarded ──▶ Planning ──▶ Execution ──▶ Closeout ──▶ Completed
                                  │
                              On Hold ──▶ Execution
                                  │
                              Cancelled
```

### 2.2 Métriques EVM (Earned Value Management)

Le modèle implémente 5 métriques de gestion de valeur acquise :

| Métrique | Formule | Signification |
|---|---|---|
| **SPI** (Schedule Performance Index) | `executed_value / budget_cost` | >1 = en avance, <1 = en retard |
| **CPI** (Cost Performance Index) | `executed_value / actual_cost` | >1 = sous budget, <1 = dépassement |
| **EAC** (Estimate at Completion) | `BAC / CPI` | Coût total estimé à finition |
| **ETC** (Estimate to Complete) | `EAC - actual_cost` | Reste à dépenser |
| **VAC** (Variance at Completion) | `BAC - EAC` | Écart final prévu |

### 2.3 Auto-Creation Triggers

Déclenchés par `write()` ou `create()` :

```
create() ──▶ [config] auto_create_analytic = True
                  └──▶ action_create_analytic_account()
                         └─── account.analytic.account

write(project_stage = 'execution') ──▶ [config] auto_create_project = True
                                          └──▶ action_create_project_project()
                                                 └─── project.project (+ analytic_account_id)
```

### 2.4 Intégrations Core Odoo

| Champ | Modèle Core | Direction |
|---|---|---|
| `analytic_account_id` | `account.analytic.account` | construction → analytic |
| `project_project_id` | `project.project` | construction → project |
| `sale_order_ids` | `sale.order` | construction ← sale (inverse) |
| `timesheet_line_ids` | `account.analytic.line` | construction ← timesheet (inverse) |
| `partner_id` | `res.partner` | Client du projet |
| `user_id` | `res.users` | Chef de projet |

---

## 3. MÉTRÉ (BOQ) — construction.boq

### 3.1 Hiérarchie

```
construction.boq
  ├── construction.boq.section (section / lot)
  │      └── construction.boq.item (item / ligne)
  │             ├── parent_id / child_ids (sous-items hiérarchiques)
  │             ├── construction.rate.analysis (analyse de prix)
  │             └── construction.material.plan (planification matériaux)
  └── sale.order (pont vers ventes)
```

### 3.2 Workflow États

```
Draft ──▶ Submitted ──▶ Approved ──▶ Revised
                           │
                     [auto_create_tasks]
                           │
                     └──▶ project.task (×N items)
```

### 3.3 Calculs Stored

| Champ | Dépendance |
|---|---|
| `item.amount` | `quantity × rate` |
| `boq.total_amount` | `SUM(item.amount)` |
| `boq.total_quantity` | `SUM(item.quantity)` |
| `boq.item_count` | `COUNT(item.*)` |

### 3.4 Pont vers Sale Order

```
action_create_sale_order()
  │
  ├── 1. Cherche/Crée un produit service générique (Construction Works)
  ├── 2. Pour chaque item BOQ (sans parent, avec amount > 0) :
  │       └── sale.order.line {
  │              product_id      ← generic product,
  │              name            ← [code] description,
  │              product_uom_qty ← item.quantity,
  │              product_uom     ← item.unit,
  │              price_unit      ← item.rate,
  │              construction_boq_item_id ← item.id
  │           }
  └── 3. sale.order { construction_boq_id, construction_project_id }
```

---

## 4. BUDGET & COMPTABILITÉ — construction.budget

### 4.1 Types de Budget

```
Original ──▶ Revised ──▶ Supplementary ──▶ Final Account
```

### 4.2 Structure Budget Line

```
construction.budget.line
  ├── budget_id ──▶ construction.budget (parent)
  ├── boq_item_id ──▶ construction.boq.item (optionnel)
  ├── resource_id ──▶ construction.resource (optionnel)
  ├── budget_post_id ──▶ account.budget.post (BI-DIRECTIONNEL ←→)
  ├── name, cost_code
  ├── quantity × unit_cost = amount (stored compute)
  └── construction_budget_line_ids (inverse sur account.budget.post)
```

### 4.3 Le Pont « Push to Accounting »

```
action_create_crossovered_budget()
  │
  ├── Prérequis : analytic_account_id doit exister sur le projet
  │
  ├── 1. Créer crossovered.budget { name, date_from/to, company }
  │
  ├── 2. Pour chaque budget.line :
  │       ├── _get_or_create_budget_post(line)
  │       │      ├── Si line.budget_post_id existe → le réutiliser
  │       │      └── Sinon :
  │       │             ├── Chercher account.budget.post par name/cost_code
  │       │             └── Si non trouvé → le créer + lier account_type='income'
  │       │                    └── line.budget_post_id = bpost.id (STORED LINK)
  │       │
  │       └── Créer crossovered.budget.line {
  │              general_budget_id   ← budget_post,
  │              analytic_account_id ← analytic du projet,
  │              planned_amount      ← line.amount
  │           }
  └──
```

### 4.4 Relation Bidirectionnelle Budget Post

```
account.budget.post ◀──── budget_post_id ────▶ construction.budget.line
                          (Many2one)                    │
                          (ondelete='restrict')          │
                                                        │
                   construction_budget_line_ids ◀────────┘
                          (One2many, inverse)
```

---

## 5. APPROVISIONNEMENTS — construction.material.request

### 5.1 Workflow

```
Draft ──▶ Submitted ──▶ Approved ──▶ Ordered ──▶ Received ──▶ Cancelled
                             │
                       action_create_purchase_order()
                             │
                             ▼
                       purchase.order (core Odoo)
                             │
                       button_confirm()
                             │
                             ▼
                       purchase.order.state = purchase
```

### 5.2 Règles Métier

- `product_id` est **required** sur `construction.material.request.line`
- `action_create_purchase_order()` filtre `line.product_id AND line.quantity > 0`
- Le champ `uom_id` est un `related='product_id.uom_id'` (auto-rempli)
- Le champ `name` est un `compute='_compute_name'` depuis `product_id.display_name`

### 5.3 Intégrations

```
construction.material.request
  ├── purchase_order.construction_material_request_id (inverse)
  ├── purchase.order.line.construction_material_request_line_id
  └── purchase.order.line.construction_boq_item_id → BOQ Item
```

---

## 6. AVANCEMENT PHYSIQUE — construction.progress

### 6.1 Workflow

```
Draft ──▶ Submitted ──▶ Approved ──▶ Cancelled
```

### 6.2 Calcul du Taux d'Exécution

```
Pour chaque progress.line :
  executed_percent = (previous_quantity + current_quantity) / total_quantity × 100

⚠ Contrainte CHECK : executed_percent <= 100
⚠ total_quantity doit être > 0 (évite division par zéro = 44 300 000%)
```

### 6.3 Agrégation au Projet

```
construction.project.progress_percent
  ──▶ compute depuis progress_ids
       │  Filtrer state = 'approved'
       │  Moyenne de executed_percent sur tous les progress records
       └── stored=True (nécessaire pour la vue SQL du dashboard)
```

---

## 7. VARIATIONS — construction.variation

### 7.1 Types

| Type | Description |
|---|---|
| `client` | Demande du client |
| `consultant` | Demande du consultant/bureau d'études |
| `site` | Condition imprévue sur site |
| `design` | Erreur/omission de conception |
| `regulatory` | Changement réglementaire |
| `other` | Autre |

### 7.2 Workflow

```
Draft ──▶ Submitted ──▶ Review ──▶ Approved ──▶ Implemented ──▶ Cancelled
                                  │
                                  └── Rejected
```

### 7.3 Calcul d'Impact Financier

```
Pour chaque variation.line :
  net_change = (revised_quantity × revised_rate) - (original_quantity × original_rate)

Pour chaque variation :
  net_change = SUM(line.net_change)
```

---

## 8. IPC (Interim Payment Certificate) — construction.ipc

### 8.1 Workflow

```
Draft ──▶ Submitted ──▶ Reviewed ──▶ Certified ──▶ Approved ──▶ Paid ──▶ Cancelled
                                                              │
                                                              ▼
                                                         account.move
                                                      (out_invoice, posted)
```

### 8.2 Calculs Stored

| Champ | Formule |
|---|---|
| `current_work_done` | `SUM(line.current_quantity × line.rate)` |
| `prev_work_done` | Depuis le dernier IPC payé (auto-calculé dans `create()`) |
| `work_done_to_date` | `prev_work_done + current_work_done` |
| `retention_amount` | `current_work_done × retention_percent / 100` |
| `net_amount` | `current_work_done - retention_amount` |
| `total_approved_amount` | `SUM(ipc_lines.approved_amount)` |

### 8.3 Génération de Numéro IPC

```
create() :
  ipc_number = _get_next_ipc_number(project_id)
             = max(ipc_number pour ce project) + 1
```

### 8.4 Pont vers Facture Client

```
action_create_invoice()
  │
  ├── 1. _get_income_account() → premier account.account avec account_type='income'
  ├── 2. Pour chaque line IPC avec amount > 0 :
  │       └── account.move.line {
  │              name       ← description + qty × rate,
  │              quantity   ← line.current_quantity,
  │              price_unit ← line.rate,
  │              account_id ← income_account
  │           }
  ├── 3. account.move {
  │        move_type    = 'out_invoice',
  │        partner_id   ← project.partner_id,
  │        invoice_line_ids = lines,
  │        ref          = 'IPC:{name}'
  │     }
  └── 4. IPC.invoice_id = invoice.id
```

---

## 9. COÛTS & CONTRÔLE — construction.cost.control

### 9.1 Entrées de Coûts (Manuelles)

```
construction.cost.entry (create manuelle)
  ├── project_id
  ├── boq_item_id → BOQ Item
  ├── resource_id → Resource
  ├── name, amount, date
  └── vendor_id (optionnel)
```

### 9.2 Cron de Synchronisation

```
cron_update_costs() (journalière)
  │
  ├── Lit :
  │     ├── Tous les cost.entry par project
  │     ├── purchase.order (matériaux achetés)
  │     ├── account.analytic.line (timesheet)
  │     └── stock.move via stock.picking (matériaux consommés)
  │
  └── Pour chaque (project, boq_item, resource) :
        └── Créer/Mettre à jour cost.control {
               planned_amount, actual_amount, variance
            }
```

---

## 10. TRÉSORERIE & PRÉVISIONS

### 10.1 Cashflow

```
construction.cashflow
  ├── flow_type : income / expense
  ├── category : client_payment / material / labor / subcontract / equipment / overhead
  ├── forecast_amount / actual_amount
  ├── is_received (pour income seulement)
  └── ipc_id (lien vers IPC si c'est une tranche de paiement)
```

### 10.2 Forecast

```
construction.forecast
  ├── forecast_type : cost / revenue
  ├── period : monthly / quarterly / yearly
  ├── planned_amount, forecast_amount, actual_amount
  └── date (date de référence pour la période)
```

---

## 11. ANALYTIQUE & TIMESHEET

### 11.1 Champs Étendus sur account.analytic.line

Héritage du modèle core `account.analytic.line` :

```
account.analytic.line
  ├── construction_project_id ──▶ construction.project
  ├── construction_boq_item_id ──▶ construction.boq.item
  ├── construction_progress_line_id ──▶ construction.progress.line
  └── cost_type : material / labor / equipment / subcontract / overhead
```

---

## 12. DASHBOARD (Vue SQL)

### 12.1 Définition

```sql
CREATE OR REPLACE VIEW construction_dashboard AS (
  SELECT
    row_number() OVER () AS id,          -- id synthétique (obligatoire pour modèle Odoo)
    p.id AS project_id,
    CURRENT_DATE AS date,
    p.contract_amount AS project_value,
    COALESCE((
      SELECT SUM(ipc.total_approved_amount)
      FROM construction_ipc ipc
      WHERE ipc.project_id = p.id
        AND ipc.state IN ('certified','approved','paid')
    ), 0.0) AS executed_value,
    p.contract_amount - executed_value AS remaining_value,
    COALESCE((
      SELECT SUM(b.grand_total)
      FROM construction_budget b
      WHERE b.project_id = p.id AND b.state = 'approved'
    ), 0.0) AS budget_cost,
    COALESCE((
      SELECT SUM(ce.amount)
      FROM construction_cost_entry ce
      WHERE ce.project_id = p.id
    ), 0.0) AS actual_cost,
    p.progress_percent,
    c.currency_id                           -- depuis res.company
  FROM construction_project p
  LEFT JOIN res_company c ON p.company_id = c.id
);
```

### 12.2 Caractéristiques

- Modèle `construction.dashboard` avec `_auto = False`
- `init()` appelée dans `post_init_hook` et manuellement après upgrade
- Read-only (vue, pas de données stockées)
- `currency_id` vient de `res_company`, PAS du champ `related` du projet
- Utilisée pour des rapports KPI et graphiques dans l'interface

---

## 13. SÉCURITÉ — 11 Groupes Hiérarchiques

### 13.1 Chaîne d'Héritage

```
auditor ──▶ finance ──▶ store_keeper ──▶ procurement ──▶ cost_controller
    ──▶ site_engineer ──▶ qs ──▶ engineer ──▶ manager ──▶ director ──▶ admin
                                                                        │
                                                   base.group_system ◀──┘
```

**Règle** : Chaque groupe `implied_ids` contient le groupe précédent. L'ordre est critique pour éviter `External ID not found`.

### 13.2 Accès par Modèle (CSV)

Chaque modèle a une ligne par groupe dans `ir.model.access.csv` :

```
construction.project, construction_project, model_construction_project, group_construction_auditor, group_construction_admin, 1,1,1,1
construction.boq, ... (même pattern)
...
```

---

## 14. CONFIGURATION

### 14.1 Paramètres (ir.config_parameter)

| Clé | Champ Settings | Défaut | Usage |
|---|---|---|---|
| `construction.auto_create_analytic` | `construction_auto_create_analytic` | True | Création auto du compte analytique à la création du projet |
| `construction.auto_create_project` | `construction_auto_create_project` | True | Création auto du projet Odoo au passage en stage execution |
| `construction.auto_create_tasks` | `construction_auto_create_tasks` | False | Création auto des tâches Odoo à l'approbation du BOQ |
| `construction.default_retention` | `construction_default_retention` | 5.0 | Pourcentage de retention par défaut sur les IPC |
| `construction.default_tax` | `construction_default_tax` | 0.0 | Taxe par défaut |
| `construction.default_analytic_plan_id` | `construction_default_analytic_plan_id` | — | Plan analytique par défaut |
| `construction.income_account_id` | `construction_income_account_id` | — | Compte de produit par défaut |
| `construction.expense_account_id` | `construction_expense_account_id` | — | Compte de charge par défaut |

---

## 15. INTÉGRATIONS — Modules Core Hérités

### 15.1 project.project

```python
project.project
  ├── construction_project_id ──▶ construction.project
  ├── construction_project_code (related = construction_project_id.code, store=True)
  └── analytic_account_id (core field, lié au analytic du construction project)
```

### 15.2 project.task

```python
project.task
  ├── boq_item_id ──▶ construction.boq.item
  └── construction_project_id (related via project_id.construction_project_id)
```

### 15.3 sale.order / sale.order.line

```python
sale.order
  ├── construction_project_id ──▶ construction.project
  ├── construction_project_code (related)
  └── construction_boq_id ──▶ construction.boq

sale.order.line
  ├── construction_project_id ──▶ construction.project
  ├── construction_boq_item_id ──▶ construction.boq.item
  └── construction_ipc_line_id ──▶ construction.ipc.line
```

### 15.4 purchase.order / purchase.order.line

```python
purchase.order
  ├── construction_project_id ──▶ construction.project
  ├── construction_project_code (related)
  └── construction_material_request_id ──▶ construction.material.request

purchase.order.line
  ├── construction_project_id ──▶ construction.project
  ├── construction_boq_item_id ──▶ construction.boq.item
  └── construction_material_request_line_id ──▶ construction.material.request.line
```

### 15.5 stock.picking / stock.move

```python
stock.picking
  ├── construction_project_id ──▶ construction.project
  ├── construction_material_issue_id ──▶ construction.material.issue
  └── construction_material_return_id ──▶ construction.material.return

stock.move
  ├── construction_project_id ──▶ construction.project
  ├── construction_boq_item_id (related via stock_picking)
  └── construction_material_request_line_id ──▶ construction.material.request.line
```

### 15.6 CRM — crm.lead

```python
crm.lead
  ├── construction_project_id ──▶ construction.project
  ├── is_converted_to_construction (Boolean)
  └── action_create_construction_project()
         ├── Crée construction.project
         ├── Lie le lead au projet
         └── Marque is_converted_to_construction = True
```

---

## 16. SÉQUENCES & PRÉFIXES

| Code Séquence | Préfixe | Modèle |
|---|---|---|
| `construction.project` | PRJ- | `construction.project` |
| `construction.boq` | BOQ- | `construction.boq` |
| `construction.material.request` | MR- | `construction.material.request` |
| `construction.material.issue` | MI- | `construction.material.issue` |
| `construction.material.return` | MRT- | `construction.material.return` |
| `construction.variation` | VO- | `construction.variation` |
| `construction.progress` | PRG- | `construction.progress` |
| `construction.ipc` | IPC- | `construction.ipc` |

---

## 17. RAPPORTS

| Rapport | Modèle | Technologie |
|---|---|---|
| Rapport BOQ | `construction.boq.report` | `report_xlsx` |
| Rapport IPC | `construction.ipc.report` | `report_xlsx` |
| Rapport Avancement | `construction.progress.report` | `report_xlsx` |

Tous les rapports utilisent la bibliothèque `report_xlsx` pour exporter en format Excel.

---

## 18. SCHÉMA COMPLET DES RELATIONS

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                       │
│  crm.lead ──▶ construction.project ──▶ account.analytic.account                      │
│       │              │                         │                                     │
│       │              ├──▶ construction.boq ────┤  (plan_id)                          │
│       │              │       ├── construction.boq.section                            │
│       │              │       │     └── construction.boq.item                         │
│       │              │       │           ├── construction.rate.analysis              │
│       │              │       │           ├── construction.material.plan              │
│       │              │       │           └── sale.order.line (via action)            │
│       │              │       │                                                       │
│       │              │       └── sale.order ──▶ account.move (invoice)               │
│       │              │                                                                 │
│       │              ├──▶ construction.budget                                         │
│       │              │       └── construction.budget.line                             │
│       │              │             └── account.budget.post (bidirectionnel)            │
│       │              │                   └── crossovered.budget.line                  │
│       │              │                                                                 │
│       │              ├──▶ construction.material.request                               │
│       │              │       └── construction.material.request.line                   │
│       │              │             └── purchase.order.line (via action)               │
│       │              │                   └── purchase.order                           │
│       │              │                                                                 │
│       │              ├──▶ construction.material.issue                                 │
│       │              │       └── stock.picking (via action)                           │
│       │              │                                                                 │
│       │              ├──▶ construction.material.return                                │
│       │              │       └── stock.picking (via action)                           │
│       │              │                                                                 │
│       │              ├──▶ construction.variation                                      │
│       │              │       └── construction.variation.line                          │
│       │              │                                                                 │
│       │              ├──▶ construction.progress                                       │
│       │              │       └── construction.progress.line                           │
│       │              │                                                                 │
│       │              ├──▶ construction.ipc                                            │
│       │              │       └── construction.ipc.line                                │
│       │              │             └── account.move (out_invoice, via action)          │
│       │              │                                                                 │
│       │              ├──▶ construction.cost.entry                                     │
│       │              │       └── construction.cost.control (via cron)                  │
│       │              │                                                                 │
│       │              ├──▶ construction.cashflow                                       │
│       │              ├──▶ construction.forecast                                       │
│       │              └──▶ project.project ──── construction.dashboard                 │
│       │                      └── project.task (×N)                                    │
│       │                                                                               │
│       └──▶ account.analytic.line (via hr_timesheet)                                   │
│                                                                                       │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 19. ANNEXE — Contraintes et Règles Métier

### 19.1 Contraintes SQL

| Modèle | Contrainte | Expression |
|---|---|---|
| `construction.project` | `code_company_unique` | `UNIQUE(code, company_id)` |
| `construction.boq` | `boq_code_project_unique` | `UNIQUE(code, project_id)` |
| `construction.budget` | `check_contingency` | `CHECK(contingency_percent >= 0 AND <= 100)` |
| `construction.progress.line` | `executed_percent <= 100` | `CHECK(executed_percent <= 100)` |

### 19.2 Validateurs Python

| Méthode | Condition |
|---|---|
| `boq.action_create_sale_order()` | `state == 'approved'` et items avec `amount > 0` |
| `budget.action_create_crossovered_budget()` | `analytic_account_id` doit exister |
| `ipc.action_create_invoice()` | `invoice_id` ne doit pas déjà exister |
| `project.action_create_analytic_account()` | `analytic_account_id` ne doit pas déjà exister |

### 19.3 Dépendances Odoo (manifest)

```python
'depends': ['report_xlsx', 'project', 'sale', 'purchase', 'stock', 'analytic',
            'account', 'hr_timesheet', 'crm']
```

---

> **Document généré le 28 juin 2026.**  
> Module : `construction_execution` v16.0  
> Modèles : 30+ (18 fichiers Python dans `models/`)  
> Groupes de sécurité : 11 (chaîne hiérarchique)
