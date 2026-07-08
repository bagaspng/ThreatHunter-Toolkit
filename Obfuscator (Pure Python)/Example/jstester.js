// jstester.js — sampel sederhana untuk uji obfuscator JS
function add(a, b) {
  return a + b;
}

function greet(name) {
  return "Halo, " + name + "!";
}

var total = add(20, 22);
console.log(greet("Dunia"));
console.log("Hasil: " + total);
