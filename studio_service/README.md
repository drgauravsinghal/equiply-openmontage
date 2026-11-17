# Studio production service

This AGPL service runs the OpenMontage hybrid pipeline through Studio. The host
meters model requests using `/v2/planning`; this service selects the stage and
supplies its director, reviewer and canonical schemas. The approved brief,
script and scene plan are persisted by the host and submitted with the production.

The execution worker writes upstream checkpoints, prepares an asset manifest and
edit decisions, calls upstream AudioMixer and VideoCompose, runs VideoCompose's
actual output review, and exports the MP4 back to Studio. The StudioHybrid
Remotion composition is a **templated** hybrid renderer, not an atelier or a new
video generation model. External generated media still requires a provider and
an approved purchase through Studio. No provider keys are stored here.

Deploy with `studio_service/Dockerfile`, repository root as the build context.
Set `STUDIO_SERVICE_TOKEN` and `SOURCE_URL` to this fork's public source URL.
Only health and source information are public. All production, upload and
download endpoints require the shared token. Media uploads use opaque UUIDs;
the service does not fetch arbitrary media URLs or execute generated code.

Runs are single-worker queued, idempotent by UUID and approved request hash.
Studio persists the input and can restore it after ephemeral storage is lost.
The host deletes a run after importing its verified export. Unclaimed files
expire after one hour; business deletion also schedules remote cleanup.

The evidence returned with each export includes stages, actual tool names,
runtime, upstream final review and the MP4 checksum. Technical review does not
replace a human assessment of the ad's creative quality.
