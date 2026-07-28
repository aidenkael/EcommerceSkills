"""Persistence facade for one selectable profit adjustment rule per product."""


class ProfitAdjustmentManager:
    def __init__(self, db_manager):
        self._db = db_manager

    def list(self, include_archived=True):
        return self._db.get_profit_adjustment_rules(include_archived)

    def enabled(self):
        return self._db.get_enabled_profit_adjustment_rules()

    def get(self, rule_id):
        return self._db.get_profit_adjustment_rule(rule_id)

    def create(self, values):
        return self._db.save_profit_adjustment_rule(values)

    def update(self, rule_id, values):
        return self._db.save_profit_adjustment_rule(values, rule_id)

    def archive_or_delete(self, rule_id):
        return self._db.archive_or_delete_profit_adjustment_rule(rule_id)

    def restore(self, rule_id):
        return self._db.restore_profit_adjustment_rule(rule_id)
