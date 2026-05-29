# Views

Views bind a domain model to a backend. They are lightweight wrappers that own no data
and copy nothing — the domain model is unchanged. Removing convenience shortcuts
(`to_numpy()`, `to_ostk()`) leaves every view fully functional.

No backend module is imported at the views module level. Backend imports are deferred to
the `to_numpy()` / `to_ostk()` shortcut method bodies.

## EphemerisView

::: orbit_data_messages.compute.views.EphemerisView

## StateView

::: orbit_data_messages.compute.views.StateView

## CovarianceView

::: orbit_data_messages.compute.views.CovarianceView
