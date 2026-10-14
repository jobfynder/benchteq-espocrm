#!/usr/bin/env bash
set -euo pipefail

cd "${STACK_PATH:-/opt/app}"

docker compose exec -T espocrm php bin/command app-check

reporting_password="$(
  sed -n 's/^METABASE_REPORTING_PASSWORD=//p' .env |
    tail -n 1 |
    tr -d '\r'
)"
test -n "$reporting_password"

docker compose exec -T -e MYSQL_PWD="$reporting_password" mysql \
  mysql --user=metabase_readonly --database=espocrm \
  --batch --skip-column-names <<'SQL'
SELECT table_name
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN (
    'c_payout', 'c_payout_c_session_log',
    'c_project', 'c_payment_block', 'c_timesheet', 'c_interview_session'
  )
ORDER BY table_name;

SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND (
    (table_name = 'lead' AND column_name IN (
      'service_type', 'referrer_id', 'referral_paid', 'bgc_type', 'bgc_fee',
      'bgc_amount_received', 'bgc_provider_id', 'bgc_provider_cost', 'bgc_status'
    ))
    OR (
      table_name = 'opportunity'
      AND column_name IN (
        'service_type',
        'referral_payout_status',
        'referral_payout_date',
        'referrer_id'
      )
    )
    OR (
      table_name = 'c_service_package'
      AND column_name IN (
        'payment_status',
        'amount_paid',
        'outstanding_balance',
        'bgc_verification_type',
        'payout_frequency',
        'renewal_due_date',
        'opportunity_id',
        'fulfilling_provider_id'
      )
    )
    OR (
      table_name = 'c_session_log'
      AND column_name IN ('session_duration', 'delivery_resource_id')
    )
  )
ORDER BY table_name, column_name;
SQL

unset reporting_password

test -f espocrm/custom/Espo/Custom/Hooks/CServicePackage/CalculateOutstandingBalance.php
test -f espocrm/custom/Espo/Custom/Hooks/CSessionLog/UpdateSessionsRemaining.php

curl --fail --silent --show-error --output /dev/null https://crm.jobfynder.com

echo "production-verification-ok"
