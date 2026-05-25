# M&H Services — Odoo 18 Development Project

## Project Overview

Custom Odoo 18 modules for M&H Services procurement approvals.

## Modules

### `approvals/dynamic_approval_workflow`
Core approval engine. Provides the `approval.mixin` abstract model for zero-touch integration into any Odoo model.

**Key models:**
- `approval.workflow.config` — per-model workflow configuration
- `approval.workflow.stage` — individual approval stages
- `approval.request` — approval request record per document
- `approval.request.line` — immutable audit trail

**Key features:**
- Domain-filtered configs (different workflows by amount, department, etc.)
- Three approver types: fixed user, security group, dynamic field
- Full state machine: draft → pending_approval → approved / rejected / returned
- Email notifications and nightly escalation cron
- OWL "My Approvals" dashboard

### `approvals/mh_approval_extension`
Extends `dynamic_approval_workflow` for four Odoo models. **Depends on:** `dynamic_approval_workflow`, `purchase`, `hr_expense`, `account`.

**Models extended:**
| Model | Blocking Action | Pattern |
|-------|----------------|---------|
| `purchase.order` | `button_approve`, `action_rfq_send` | Direct mixin inheritance |
| `hr.expense` / `hr.expense.sheet` | Approval flow via mixin | Direct mixin inheritance |
| `account.move` | `action_post` | Inline field re-declaration |
| `account.payment` | `action_post` | Inline field re-declaration |

**State flow (all models):**
```
draft → pending_approval → approved
                        ↘ rejected
                        ↘ returned
```

## Development Patterns

### Pattern 1: Direct Mixin Inheritance
Use when the target model has no field name conflicts with `approval_state` or `approval_request_count`.

```python
class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "approval.mixin", "mail.thread"]
```

### Pattern 2: Inline Field Re-declaration
Use when the target model already has fields that would conflict (e.g., `account.move` has `transaction_ids`).

```python
class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move"]

    # Re-declare mixin fields inline to avoid collision
    approval_state = fields.Selection(...)
    approval_request_count = fields.Integer(...)

    # Also inline helper methods from the mixin
    def _get_approval_config(self): ...
    def action_submit_for_approval(self): ...
    def action_view_approval_requests(self): ...
```

## Odoo.sh Workflow

1. Push to `develop` branch → Odoo.sh builds development stage
2. Install modules via **Apps → Update Apps List → Install**
3. Configure workflows via **Approval Workflows** menu
4. Create feature branches: `git checkout -b feature/my-feature`
5. Merge to `develop` for testing, `main` for production

## Useful Commands

```bash
# Update apps list in Odoo.sh shell
ssh odoodb@usufahmedk.odoo.sh "cd /mnt/extra-addons && odoo-bin -u dynamic_approval_workflow,mh_approval_extension -d mh approval"

# View Odoo logs
ssh odoodb@usufahmedk.odoo.sh "tail -100 /var/log/odoo/odoo.log"
```