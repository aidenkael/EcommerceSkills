"""Dynamic forwarder service.  The database remains the source of truth."""


class ForwarderManager:
    def __init__(self, db_manager):
        self._db = db_manager

    def list(self, include_archived=True):
        return self._db.get_all_routes(include_archived=include_archived)

    def enabled(self):
        return self._db.get_enabled_routes()

    def create(self, values):
        return self._db.save_route(values)

    def update(self, route_id, values):
        return self._db.save_route(values, route_id=route_id)

    def set_enabled(self, route_id, enabled):
        route = self._db.get_route_rates(route_id)
        if route is None:
            raise ValueError("货代不存在")
        route["is_enabled"] = bool(enabled)
        return self.update(route_id, route)

    def is_referenced(self, route_id):
        return self._db.route_is_referenced(route_id)

    def archive_or_delete(self, route_id):
        return self._db.archive_or_delete_route(route_id)

    def restore(self, route_id):
        route = self._db.get_route_rates(route_id)
        if route is None:
            raise ValueError("货代不存在")
        route["is_archived"] = False
        route["is_enabled"] = False
        return self.update(route_id, route)
