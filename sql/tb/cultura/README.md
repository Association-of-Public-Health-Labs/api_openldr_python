# TBCultura materialized dataset

This directory contains the production deployment assets for the materialized
TB culture dataset.

## Data contract

- Source: `[OpenLDRData].[dbo].[viewTB_Cultura]`
- Target: `[TBData].[dbo].[TBCultura]`
- Business key: `RequestID`
- ORM bind: `tb`
- Synchronization: full reconciliation, not a `DateTimeStamp` watermark
- Execution host: a T-SQL SQL Server Agent job step; no custom stored procedure

The target contains all 130 source columns, including patient-identifying and
free-text clinical data. Access to the table and its backups must therefore be
restricted to the same population that is authorized to read the source view.
The synchronization log stores counts and sanitized errors only; it never
stores source row values.

The source view is already flat and currently returns one row per `RequestID`,
so no table-valued function is needed between the view and the materialized
table.

## Deployment assets

- `001_create_tbcultura_table.sql` creates the materialized table, compact
  rowstore indexes, and aggregate-only synchronization audit table.
- `002_create_tbcultura_sql_agent_job.sql` creates the SQL Server Agent job.
  The job step contains the complete staging and reconciliation command inline.
  Its six `nvarchar(max)` chunks are protected by a normalized 31,714-byte
  assembly check before the job step is created or updated.
- `003_verify_tbcultura_deployment.sql` performs read-only metadata, aggregate,
  integrity, job, and latest-run checks. It neither starts the job nor changes
  source or target data.

There is deliberately no `usp_SyncTBCultura` procedure. Keeping the
synchronization command in the Agent step avoids deploying an additional
programmable object while retaining a single, server-side execution point.

## Deployment order

Run the scripts in SQL Server Management Studio or `sqlcmd` using a login that
can create objects in `TBData`, read the source view, and manage SQL Server
Agent jobs:

1. `001_create_tbcultura_table.sql`
2. `002_create_tbcultura_sql_agent_job.sql`
3. Start the job manually for the initial full reconciliation:

   ```sql
   USE [msdb];
   EXEC [dbo].[sp_start_job]
       @job_name = N'TB - Sync TBCultura';
   ```

   Wait for the job to finish and confirm its aggregate status:

   ```sql
   SELECT TOP (1)
       [RunID],
       [StartedAt],
       [CompletedAt],
       [Status],
       [SourceRows],
       [TargetRowsAfter],
       [InsertedRows],
       [UpdatedRows],
       [DeletedRows],
       [DurationMs],
       [ErrorNumber],
       [ErrorMessage]
   FROM [TBData].[dbo].[TBCulturaSyncRun]
   ORDER BY [RunID] DESC;
   ```

4. `003_verify_tbcultura_deployment.sql`

The job is scheduled every four hours at `00:30`, `04:30`, `08:30`, `12:30`,
`16:30`, and `20:30`. The manual start is required to perform and inspect the
initial load immediately instead of waiting for the first scheduled interval.

## Synchronization guarantees

Each run:

1. Obtains an exclusive application lock so two instances cannot overlap.
2. Reads the complete source view once into a temporary staging table.
3. Rejects an empty source, null keys, or duplicate `RequestID` values.
4. Compares source and target values with a null-safe `EXCEPT`.
5. Updates changed rows, inserts new rows, and removes rows missing from the
   source.
6. Rejects an unexpectedly large deletion unless a DBA explicitly overrides
   the guard.
7. Commits all target changes atomically and records aggregate run metrics.

The full reconciliation is intentional. `viewTB_Cultura.DateTimeStamp` comes
from an anchor request and does not reliably advance when later laboratory,
patient, or dictionary data changes.

Operational columns (`EPTS`, SMS fields, and `CreatedAt`) are not overwritten
by source synchronization. `UpdatedAt` changes only when a source row changes.

## Failure recovery

- A failure while staging leaves `TBCultura` unchanged.
- A failure during data modification rolls the transaction back.
- A later successful run reconciles the complete source again.
- Lock contention is recorded as `SKIPPED`; the next scheduled run retries the
  complete reconciliation.
- If the deletion guard stops a legitimate large correction, investigate the
  source first. Any one-time override of the inline `@AllowLargeDelete` guard
  must be an audited DBA change to the Agent step and must be reverted
  immediately after the approved run.

Do not use that override for an empty or unexpectedly truncated source.

## SQL Server compatibility

The scripts target SQL Server 2014 with database compatibility level 120. They
therefore avoid `CREATE OR ALTER`, `DROP IF EXISTS`, `FOR JSON`, `STRING_AGG`,
and `MERGE`.
