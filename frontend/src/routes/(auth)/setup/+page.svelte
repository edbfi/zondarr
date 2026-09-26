<script lang="ts">
import SetupWizard from '$lib/components/setup/setup-wizard.svelte';
import type { PageData } from './$types';

const { data }: { data: PageData } = $props();
</script>

<SetupWizard
	initialStep={data.onboardingStep}
	tokenAvailable={data.tokenAvailable}
	tokenError={data.tokenError}
/>
