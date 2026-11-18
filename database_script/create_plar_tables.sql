-- PLAR (Post Loan-Disbursement Assurance Review) - new tables only.
-- Nothing here changes an existing table. Safe to run more than once.

CREATE TABLE IF NOT EXISTS tbl_plar_run (
    run_id          SERIAL PRIMARY KEY,
    mis_month       DATE NOT NULL UNIQUE,              -- first day of the month under review
    sample_locked   SMALLINT NOT NULL DEFAULT 0,       -- 1 once the sample has been generated
    locked_by       INTEGER,
    locked_date     TIMESTAMP,
    created_by      INTEGER,
    created_date    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Sample % per region for a run (5 by default, up to 10)
CREATE TABLE IF NOT EXISTS tbl_plar_region_target (
    target_id       SERIAL PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES tbl_plar_run(run_id) ON DELETE CASCADE,
    region_id       INTEGER NOT NULL,                  -- tbl_national_council_distribution id
    sample_pct      NUMERIC(4,1) NOT NULL DEFAULT 5,
    UNIQUE (run_id, region_id)
);

CREATE TABLE IF NOT EXISTS tbl_plar_sample (
    sample_id        SERIAL PRIMARY KEY,
    run_id           INTEGER NOT NULL REFERENCES tbl_plar_run(run_id) ON DELETE CASCADE,
    loan_no          VARCHAR(40) NOT NULL,
    pre_disb_temp_id INTEGER,                          -- matched EGS application (NULL when unmatched)
    region_id        INTEGER,
    region_name      VARCHAR(120),
    branch_code      VARCHAR(20),
    branch_name      VARCHAR(160),
    product_code     VARCHAR(30),
    disbursed_amount NUMERIC(15,2),
    basis            VARCHAR(15) NOT NULL,             -- Random / Risk-Based
    why              TEXT,
    risk_score       NUMERIC(7,2),
    created_by       INTEGER,
    created_date     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, loan_no)
);

CREATE TABLE IF NOT EXISTS tbl_plar_review (
    review_id       SERIAL PRIMARY KEY,
    sample_id       INTEGER NOT NULL UNIQUE REFERENCES tbl_plar_sample(sample_id) ON DELETE CASCADE,
    checks          JSONB NOT NULL DEFAULT '{}'::jsonb,
    overall_status  VARCHAR(30) NOT NULL DEFAULT 'Review In Progress',
    issue_category  VARCHAR(40),
    issue_severity  VARCHAR(15),
    observation     TEXT,
    reviewed_by     INTEGER,
    reviewed_date   TIMESTAMP,
    modified_date   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tbl_plar_action (
    action_id       SERIAL PRIMARY KEY,
    review_id       INTEGER REFERENCES tbl_plar_review(review_id) ON DELETE SET NULL,
    sample_id       INTEGER REFERENCES tbl_plar_sample(sample_id) ON DELETE SET NULL,
    loan_no         VARCHAR(40),
    region_name     VARCHAR(120),
    branch_name     VARCHAR(160),
    category        VARCHAR(40),
    severity        VARCHAR(15),
    action_text     TEXT,
    owner_name      VARCHAR(120),
    owner_user_id   INTEGER,
    due_date        DATE,
    status          VARCHAR(20) NOT NULL DEFAULT 'Open',   -- Open / In Progress / Resolved / Closed
    escalated       SMALLINT NOT NULL DEFAULT 0,
    escalated_date  TIMESTAMP,
    last_reminder   TIMESTAMP,
    closed_date     TIMESTAMP,
    created_by      INTEGER,
    created_date    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tbl_plar_action_evidence (
    evidence_id     SERIAL PRIMARY KEY,
    action_id       INTEGER NOT NULL REFERENCES tbl_plar_action(action_id) ON DELETE CASCADE,
    file_name       VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500) NOT NULL,
    uploaded_by     INTEGER,
    uploaded_date   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Reconciliation exceptions: only the decision is stored (Pending until a reviewer resolves it with a note).
-- case_key = loan number, or APP<application id> for "lien confirmation pending" (no loan exists yet).
CREATE TABLE IF NOT EXISTS tbl_plar_exception_case (
    case_id          SERIAL PRIMARY KEY,
    mis_month        DATE NOT NULL,
    exception_code   VARCHAR(20) NOT NULL,
    case_key         VARCHAR(60) NOT NULL,
    loan_no          VARCHAR(40),
    pre_disb_temp_id INTEGER,
    status           VARCHAR(12) NOT NULL DEFAULT 'Pending',     -- Pending / Resolved
    resolution_note  TEXT,
    resolved_by      INTEGER,
    resolved_date    TIMESTAMP,
    UNIQUE (mis_month, exception_code, case_key)
);
CREATE TABLE IF NOT EXISTS tbl_plar_exception_evidence (
    evidence_id     SERIAL PRIMARY KEY,
    case_id         INTEGER NOT NULL REFERENCES tbl_plar_exception_case(case_id) ON DELETE CASCADE,
    file_name       VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500) NOT NULL,
    uploaded_by     INTEGER,
    uploaded_date   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- The bank lien-list upload was dropped: the lien letter is EGS's own approval email (email_status = 2).
DROP TABLE IF EXISTS tbl_plar_lien_row;
DROP TABLE IF EXISTS tbl_plar_lien_batch;

-- Audit trail: PLAR tables only
CREATE TABLE IF NOT EXISTS tbl_plar_audit (
    audit_id        SERIAL PRIMARY KEY,
    entity          VARCHAR(40) NOT NULL,
    entity_id       VARCHAR(40),
    action          VARCHAR(80) NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    user_id         INTEGER,
    user_name       VARCHAR(120),
    created_date    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_plar_audit_entity ON tbl_plar_audit (entity, entity_id);
