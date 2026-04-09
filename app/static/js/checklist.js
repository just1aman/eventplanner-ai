// Checklist toggle functionality
(function() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

    document.querySelectorAll('.checklist-toggle').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const itemId = this.dataset.itemId;
            const listItem = document.getElementById(`checklist-${itemId}`);

            fetch(`/api/checklist/${itemId}/toggle`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
            })
            .then(resp => resp.json())
            .then(data => {
                if (data.status === 'success') {
                    if (data.completed) {
                        listItem.classList.add('completed');
                    } else {
                        listItem.classList.remove('completed');
                    }
                }
            })
            .catch(() => {
                // Revert on error
                this.checked = !this.checked;
            });
        });
    });
})();
