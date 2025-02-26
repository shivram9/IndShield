const hamBurger = document.querySelector(".toggle-btn");

hamBurger.addEventListener("click", function () {
  document.querySelector("#sidebar").classList.toggle("expand");
});


document.addEventListener("DOMContentLoaded", function () {
  // Load Lottie.js for animations
  const script = document.createElement("script");
  script.src = "https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.9.6/lottie.min.js";
  script.onload = initLottieAnimations;
  document.body.appendChild(script);

  function initLottieAnimations() {
      document.querySelectorAll("[id^='json-animation-']").forEach(animationDiv => {
          const camId = animationDiv.id.split("-").pop();
          lottie.loadAnimation({
              container: animationDiv,
              renderer: "svg",
              loop: true,
              autoplay: true,
              path: "static/img/CCTV.json"
          });

          // Check if camera feed is available
          checkCameraConnection(camId);
      });
    }
});

function checkCameraConnection(camId) {
    const videoFrame = document.getElementById(`video-${camId}`);
    const loadingDiv = document.getElementById(`loading-animation-${camId}`);

    function tryLoading() {
        videoFrame.src = `/video_feed/${camId}`; // Reload the video source
    }

    videoFrame.onload = function () {
        loadingDiv.style.display = "none"; // Hide animation
        videoFrame.style.display = "block"; // Show video feed
    };

    videoFrame.onerror = function () {
        videoFrame.style.display = "none"; // Hide video
        loadingDiv.style.display = "flex"; // Show animation
        setTimeout(tryLoading, 5000); // Retry after 5 sec
    };

    tryLoading(); // Try loading initially
    
}

document.addEventListener("DOMContentLoaded", function () {
    // Looping status messages
    const statusMessages = [
        "Connecting...",
        "IP Address Retrieving...",
        "Database Connect...",
        "Advanced AI System On...",
        "System Optimized..."
    ];
    let statusIndex = 0;

    function updateStatus() {
        document.getElementById("status-text").innerText = statusMessages[statusIndex];
        statusIndex = (statusIndex + 1) % statusMessages.length;
    }

    setInterval(updateStatus, 1500); // Change message every 1.5 seconds
    updateStatus(); // Initial update

    // Hide JSON animation after 2 seconds
    setTimeout(() => {
        document.querySelectorAll(".camera-loading").forEach(el => el.style.display = "none");
    }, 2000);

    // Auto-adjust camera iframe height
    function adjustCameraHeight() {
        document.querySelectorAll(".video-feed").forEach(iframe => {
            iframe.style.height = window.innerHeight + "px";
        });
    }

    adjustCameraHeight(); // Initial adjustment
    window.addEventListener("resize", adjustCameraHeight);
});
