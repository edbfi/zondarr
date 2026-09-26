<script lang="ts">
import LogEntry from './log-entry.svelte';

let { onSelect }: { onSelect: (seq: number) => void } = $props();
</script>

<LogEntry
	entry={{
	seq: 42,
	timestamp: '2026-01-01T00:00:00Z',
	level: 'INFO',
	logger_name: 'ci',
	message: 'Example log entry',
	fields: {}
}}
	selected={true}
	{onSelect}
/>
