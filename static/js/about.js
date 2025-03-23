document.addEventListener("DOMContentLoaded", function () {
    let members = document.querySelectorAll(".member");

    members.forEach(member => {
        member.addEventListener("mouseover", function () {
            member.style.boxShadow = "0px 8px 20px rgba(0, 0, 0, 0.3)";
        });

        member.addEventListener("mouseout", function () {
            member.style.boxShadow = "0px 5px 10px rgba(0, 0, 0, 0.2)";
        });
    });
});
