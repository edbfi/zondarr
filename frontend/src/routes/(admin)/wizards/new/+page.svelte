<script lang="ts">
/**
 * Create wizard page.
 *
 * Displays the wizard builder for creating a new wizard.
 *
 * @module routes/(admin)/wizards/new/+page
 */

import { goto } from '$app/navigation';
import type { WizardDetailResponse } from '$lib/api/client';
import { WizardBuilder } from '$lib/components/wizard';

/**
 * Handle save - navigate to the wizard editor.
 */
function handleSave(wizard: WizardDetailResponse) {
	goto(`/wizards/${wizard.id}`);
}

/**
 * Handle cancel - go back to wizard list.
 */
function handleCancel() {
	goto('/wizards');
}
</script>

<WizardBuilder onSave={handleSave} onCancel={handleCancel} />
