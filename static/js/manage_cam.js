document.addEventListener('DOMContentLoaded', function () {
    // Selector helper
    const select = (el) => document.querySelector(el);

    // Get all checkboxes and indicators
    const fireCheckbox = select('#fire-checkbox');
    const poseAlertCheckbox = select('#pose-alert-checkbox');
    const restrictedZoneCheckbox = select('#restricted-zone-checkbox');
    const safetyGearCheckbox = select('#safety-gear-checkbox');

    const fireIndicator = select('#fire-indicator');
    const poseAlertIndicator = select('#pose-alert-indicator');
    const restrictedZoneIndicator = select('#restricted-zone-indicator');
    const safetyGearIndicator = select('#safety-gear-indicator');

    /**
     * Function to update the status of an indicator
     * @param {HTMLInputElement} checkbox - Checkbox element to track state.
     * @param {HTMLElement} indicator - Indicator element to update status.
     */
    const updateIndicator = (checkbox, indicator) => {
        if (checkbox.checked) {
            indicator.textContent = 'Active';
            indicator.style.color = 'green';
        } else {
            indicator.textContent = 'Inactive';
            indicator.style.color = 'red';
        }
    };

    // Add event listeners for each checkbox
    [fireCheckbox, poseAlertCheckbox, restrictedZoneCheckbox, safetyGearCheckbox].forEach((checkbox, index) => {
        const indicators = [fireIndicator, poseAlertIndicator, restrictedZoneIndicator, safetyGearIndicator];
        checkbox.addEventListener('change', () => updateIndicator(checkbox, indicators[index]));
    });

    // Initialize indicators based on current checkbox states
    updateIndicator(fireCheckbox, fireIndicator);
    updateIndicator(poseAlertCheckbox, poseAlertIndicator);
    updateIndicator(restrictedZoneCheckbox, restrictedZoneIndicator);
    updateIndicator(safetyGearCheckbox, safetyGearIndicator);
});


document.addEventListener('DOMContentLoaded', function () {
    /**
     * Fetch hand gesture alert data from the backend
     * @param {string} cameraId - The ID of the camera to fetch hand gesture alert data for.
     * @returns {Promise<Object>} Hand gesture alert data from the backend.
     */
    const fetchHandGestureAlert = async (cameraId) => {
        try {
            const response = await fetch(`/hand_alert/${cameraId}`);
            if (!response.ok) throw new Error(`Failed to fetch hand gesture alert for Camera ID: ${cameraId}`);
            return await response.json();
        } catch (error) {
            console.error(`Error fetching hand gesture alert for Camera ID ${cameraId}:`, error);
            return { alert: false, gesture: "Safe" }; // Default response in case of error
        }
    };

    /**
     * Update the hand gesture alert overlay for a specific camera
     * @param {string} cameraId - The ID of the camera to update the alert for.
     */
    const updateHandGestureAlert = async (cameraId) => {
        const alertDiv = document.getElementById(`hand-alert-${cameraId}`);
        if (!alertDiv) {
            console.warn(`Alert container for Camera ID ${cameraId} not found.`);
            return;
        }

        const data = await fetchHandGestureAlert(cameraId);
        if (data.alert) {
            alertDiv.textContent = `Gesture Detected: ${data.gesture}`;
            alertDiv.style.color = data.gesture === "Thumbs Down" ? 'red' : 'green';
            alertDiv.style.display = 'block';

            // Play alert sound for "Thumbs Down"
            if (data.gesture === "Thumbs Down") {
                const alertSound = new Audio('/static/sounds/alert.mp3');
                alertSound.play();
            }
        } else {
            alertDiv.textContent = 'No Gesture Detected';
            alertDiv.style.color = 'green';
            alertDiv.style.display = 'block';
        }
    };

    // Refresh hand gesture alerts for all cameras periodically
    setInterval(() => {
        const cameraIds = [...document.querySelectorAll('.hand-alert')].map(div => div.id.split('-')[2]);
        cameraIds.forEach(updateHandGestureAlert);
    }, 5000); // Refresh every 5 seconds
});
