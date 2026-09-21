{
  "schema": "SEI_PL1_CLEANUP_EXECUTION_REPORT_V1",
  "executed_utc": "2026-08-28T16:50:00.733482+00:00",
  "authorization": "OWNER_DIRECTIVE_20260828_SESSION",
  "mode": "QUARANTINE_COMPLETE__HARD_DELETE_NOT_AUTHORIZED",
  "actions": {
    "quarantine": {
      "moved": 220,
      "bytes": 331040589,
      "root": "F:\\_SEI_RETIREMENT_QUARANTINE_20260828",
      "hard_delete_forbidden_before": "2026-09-15"
    },
    "ephemeral": {
      "deleted": 94,
      "bytes": 2727998,
      "skipped_fail_closed": 132,
      "skip_causes": [
        "text/manifest reference positive (incl. PRE_EXECUTION_HASHES evidence)",
        "generic basename false-positive conservative hold"
      ]
    },
    "hold_untouched": 26670,
    "errors": []
  },
  "integrity": {
    "head_unchanged": true,
    "protected_sha_ok": true,
    "quarantine_files": 220
  },
  "verdict": "QUARANTINE_COMPLETE__HARD_DELETE_NOT_AUTHORIZED",
  "do_not_claim": [
    "mechanical release complete",
    "competition submission complete",
    "paper complete"
  ],
  "next": [
    "owner confirmation of 3 absent roots",
    "hard-delete authorization >= 2026-09-15 with manifest sha256"
  ]
}