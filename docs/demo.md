# Three-minute demo

1. Load the sample CSV and click **Suggest mappings**. Observe each source field's learned destination, candidate scores, and sample evidence.
2. Inspect the leading-zero ZIP and the ambiguous date `02/03/2026`. The system will not guess its locale.
3. Click **Validate reviewed mapping**. The sample has one valid row and three quarantined rows. Both copies of C-1002 are rejected, rather than picking one silently.
4. Download the validated CSV. Avery's `02108` ZIP remains intact and the money value is canonical.
5. Reopen the run from history. Review state and audit events survive a page refresh.

Interview discussion: why combine learned suggestions with strict validation? Why enforce uniqueness globally? Why reject all duplicates? What additional evidence would be needed to calibrate confidence? What changes for a multi-tenant integration service?
