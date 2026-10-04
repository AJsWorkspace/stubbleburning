// Project Title

const text =
"Stubble Burning Monitoring System";

let index = 0;

// Typing Effect

function typeWriter() {

    if(index < text.length){

        document.getElementById("title").innerHTML +=
        text.charAt(index);

        index++;

        setTimeout(typeWriter, 70);
    }

}

// Run when page loads

window.onload = function(){

    typeWriter();

};

// Start Analysis Button

function startAnalysis(){

    window.location.href = "/dashboard";

}