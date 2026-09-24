-- Mounted into the compose postgres container's entrypoint.
-- Creates the ai-service database next to api-service's, so the two services
-- never share a schema. Runs only when the data volume is empty.
SELECT 'CREATE DATABASE numm_ai OWNER ' || current_user
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'numm_ai')\gexec
