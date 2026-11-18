-- PLAR page permissions (same pattern as add_exception_report_permission.sql).
-- Executive Approver (3) and Admin (4) open every PLAR page by their rights already.
--   /plar-dashboard : lets an admin also show the PLAR dashboard to another user
--   /plar-review    : the "PLAR reviewer" permission - opens the work screens (reconciliation, exceptions,
--                     sampling, case review, corrective actions) and allows saving reviews.
-- NOT run automatically. Run it when you are ready to grant PLAR access from "User Permissions".
INSERT INTO tbl_web_permissions (title, route, permission_key, description, status, created_by, created_date, modified_by, modified_date, category)
SELECT 'PLAR Dashboard', '/plar-dashboard', 'page.plar_dashboard.access',
       'Post-Disbursement Assurance Review dashboard', 1, NULL, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP, 3
WHERE NOT EXISTS (SELECT 1 FROM tbl_web_permissions WHERE route = '/plar-dashboard');

INSERT INTO tbl_web_permissions (title, route, permission_key, description, status, created_by, created_date, modified_by, modified_date, category)
SELECT 'PLAR Reviewer', '/plar-review', 'page.plar_review.access',
       'Post-Disbursement Assurance Review work screens and review rights', 1, NULL, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP, 3
WHERE NOT EXISTS (SELECT 1 FROM tbl_web_permissions WHERE route = '/plar-review');
