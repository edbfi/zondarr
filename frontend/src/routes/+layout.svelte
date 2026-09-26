<script lang="ts">
import 'virtual:uno.css';
import '../app.css';
import { ModeWatcher } from 'mode-watcher';
import type { Snippet } from 'svelte';
import { browser } from '$app/environment';
import { api } from '$lib/api/client';
import favicon from '$lib/assets/favicon.svg';
import { Toaster } from '$lib/components/ui/sonner';
import { setProviders } from '$lib/stores/providers.svelte';
import type { LayoutData } from './$types';

const { data, children }: { data: LayoutData; children: Snippet } = $props();

let providersFetched = false;

$effect(() => {
	if (browser && !providersFetched) {
		providersFetched = true;
		api
			.GET('/api/v1/providers')
			.then(({ data }) => {
				if (data) setProviders(data);
			})
			.catch(() => {
				providersFetched = false;
			});
	}
});
</script>

<svelte:head>
	<title>Zondarr</title>
	<link rel="icon" type="image/svg+xml" href={favicon}>
</svelte:head>

<ModeWatcher />
<Toaster richColors closeButton />

{@render children()}
