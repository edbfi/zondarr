<script lang="ts">
/**
 * Logs page — real-time log viewer.
 *
 * Streams backend structlog output via SSE with filtering and search.
 * No +page.ts needed — data comes from SSE, not REST.
 */

import LogViewer from '$lib/components/logs/log-viewer.svelte';
</script>

<div class="space-y-6">
	<p class="text-cr-text-muted">
		Real-time structured log output from the backend, streamed via SSE.
	</p>
	<LogViewer />
</div>
