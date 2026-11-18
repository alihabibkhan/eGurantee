-- Task 005: Student Finance auto-approval - challan check, matrix exception and step tracking.
-- Additive only; safe to run more than once. Run BEFORE deploying the new code.

-- What each uploaded picture is (the 4th part of the file name, e.g. economics_picture1 = the fee challan)
ALTER TABLE tbl_pre_disbursement_application_images ADD COLUMN IF NOT EXISTS image_type VARCHAR(100);
CREATE INDEX IF NOT EXISTS idx_pd_app_images_app_type
    ON tbl_pre_disbursement_application_images (application_no, image_type);

-- Step-by-step trail of every auto-approval decision (shown on the Auto Approved Monitor)
ALTER TABLE tbl_auto_approval_log ADD COLUMN IF NOT EXISTS steps TEXT;                 -- JSON list of {step, result, detail}
ALTER TABLE tbl_auto_approval_log ADD COLUMN IF NOT EXISTS is_exception SMALLINT;      -- 1 = approved with a matrix exception
ALTER TABLE tbl_auto_approval_log ADD COLUMN IF NOT EXISTS exception_reason TEXT;
ALTER TABLE tbl_auto_approval_log ADD COLUMN IF NOT EXISTS challan_amount NUMERIC(14,2);
ALTER TABLE tbl_auto_approval_log ADD COLUMN IF NOT EXISTS sent_to_executive SMALLINT; -- 1 = third-level approval, waiting in the executive bucket
