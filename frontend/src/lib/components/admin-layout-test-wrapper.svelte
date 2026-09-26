<script lang="ts">
import AdminLayout from '../../routes/(admin)/+layout.svelte';

const testData = {
	user: {
		id: '00000000-0000-0000-0000-000000000000',
		username: 'testadmin',
		email: null,
		auth_method: 'local'
	}
};
</script>

<AdminLayout data={testData}>
	{#snippet children()}
		<div data-testid="test-content">Test Content</div>
	{/snippet}
</AdminLayout>
