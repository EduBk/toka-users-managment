#!/bin/sh
# Renders the RabbitMQ definitions file from the template using the credentials
# from the environment, then starts the broker.
#
# `load_definitions` disables the image's default user seeding, so the user must
# be part of the definitions. Its hash cannot be versioned: it is computed here.

set -eu

: "${RABBITMQ_DEFAULT_USER:?RABBITMQ_DEFAULT_USER is required}"
: "${RABBITMQ_DEFAULT_PASS:?RABBITMQ_DEFAULT_PASS is required}"

case "$RABBITMQ_DEFAULT_USER" in
    *[!A-Za-z0-9._-]*)
        echo "RABBITMQ_DEFAULT_USER contains unsupported characters" >&2
        exit 1
        ;;
esac

password_hash="$(rabbitmqctl hash_password "$RABBITMQ_DEFAULT_PASS" | tail -n 1)"

sed \
    -e "s|__RABBITMQ_USER__|$RABBITMQ_DEFAULT_USER|g" \
    -e "s|__RABBITMQ_PASSWORD_HASH__|$password_hash|g" \
    /etc/rabbitmq/definitions.template.json > /etc/rabbitmq/definitions.json

exec docker-entrypoint.sh "$@"
