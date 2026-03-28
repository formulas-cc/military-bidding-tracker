#!/bin/bash
cd /mnt/d/Projects/military-bidding-tracker
export DB_PATH=/tmp/test_bids_dev.db
python3 -m pytest tests/ -v --tb=short 2>&1
echo "EXIT_CODE:$?"
