#!/bin/bash

while IFS='=' read -r key value
do
  if [[ -n $key && -n $value ]]; then
    command="export $key=\"$value\""
    echo $command >> export_variables.sh
  fi
done < ".env"

source export_variables.sh
rm export_variables.sh

echo "All variables exported"
