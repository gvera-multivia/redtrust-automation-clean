const getBrowserName = () => {
  let browserInfo = navigator.userAgent;
  let browser;
  if (browserInfo.includes('Edg')) {
    browser = 'Edge';
  } else if (browserInfo.includes('Chrome')) {
    browser = 'Chrome';
  } else if (browserInfo.includes('Firefox')) {
    browser = 'Firefox'
  } else {
    browser = 'Chrome'
  }
  return browser;
}

// always waits the document to be loaded when shown
document.addEventListener('DOMContentLoaded', function () {
  let literals = {
    es: {
      title: "Configuración requerida",
      p1: "Para continuar, <b class='text-error'>necesita habilitar algún permiso</b>. Antes de proceder, es imprescindible que active las opciones que permiten a la extensión acceder al modo incógnito: ",
      li1: "Haga clic aquí para abrir la configuración.",
      li2: "Marque (Permitir en incógnito), como se indica en la imagen."
    },
    ca: {
      title: "Configuració requerida",
      p1: "Per continuar, <b class='text-error'>cal habilitar algun permís</b>. Abans de procedir, és imprescindible que activeu les opcions que permeten a l'extensió accedir al mode incògnit: ",
      li1: "Feu clic aquí per obrir la configuració.",
      li2: "Marqueu (Permet en mode d'incògnit), com s'indica a la imatge.",
      alt: "imatge exemple activació mode incògnit"
    },
    pt: {
      title: "Configuração necessária",
      p1: "Para continuar, <b class='text-error'>você precisa ativar algumas permissões</b>. Antes de continuar, é necessário que você ative as opções que permitem que a extensão acesse o modo de navegação anônima: ",
      li1: "Clique aqui para abrir as configurações.",
      li2: "Marque (Permitir na navegação anônima), conforme mostrado na imagem.",
      alt: "exemplo de imagem ativação do modo anônimo"
    },
    en: {
      title: "Configuration required",
      p1: "To proceed, <b class='text-error'>please enable the required permissions</b>. It is essential to activate the options that allow the extension to access incognito mode before continuing: ",
      li1: "Click here to open settings.",
      li2: "Select (Allow in incognito), as shown in the image.",
      alt: "image example activation incognito mode"
    },
  }

  function setLiterals() {
    const browserName = getBrowserName();
    let multiLangContainer = document.getElementById("multiLangContainer");
    // @ts-ignore
    let userLang = navigator.language || navigator.userLanguage;
    let lang = userLang.substring(0, 2).toLowerCase();
    let img_name = `${lang}_${browserName}_Incognito.png`;
    if (lang === "es") {
      if (browserName === "Edge") {
        literals.es.li2 = "Marque (Permitir en InPrivate), como se indica en la imagen.";
      }
      if (browserName === "Firefox") {
        // @ts-ignore
        multiLangContainer.innerHTML = `<p>${literals.es.p1}</p><p><a href="#" id="Config_Button">${literals.es.li1}</a></p>`;
      }
      else {
        // @ts-ignore
        multiLangContainer.innerHTML = `<p>${literals.es.p1}</p><ol><li><a href="#" id="Config_Button">${literals.es.li1}</a></li><li>${literals.es.li2}</li></ol><img src="./icons/${img_name}" alt="${literals.es.alt}">`;
      }
    } else if (lang === "ca") {
      if (browserName === "Edge") {
        literals.ca.li2 = "Marqueu (Permet a la funció InPrivate), com s'indica a la imatge.";
      }
      if (browserName === "Firefox") {
        // @ts-ignore
        multiLangContainer.innerHTML = `<p>${literals.ca.p1}</p><p><a href="#" id="Config_Button">${literals.ca.li1}</a></p>`;
      }
      else {
        // @ts-ignore
        multiLangContainer.innerHTML = `<p>${literals.ca.p1}</p><ol><li><a href="#" id="Config_Button">${literals.ca.li1}</a></li><li>${literals.ca.li2}</li></ol><img src="./icons/${img_name}" alt="${literals.ca.alt}">`;
      }
    } else if (lang === "pt") {
      if (browserName === "Edge") {
        literals.pt.li2 = "Marque (Permitir no modo InPrivate), conforme mostrado na imagem.";
      }
      if (browserName === "Firefox") {
        // @ts-ignore
        multiLangContainer.innerHTML = `<p>${literals.pt.p1}</p><p><a href="#" id="Config_Button">${literals.pt.li1}</a></p>`;
      }
      else {
        // @ts-ignore
        multiLangContainer.innerHTML = `<p>${literals.pt.p1}</p><ol><li><a href="#" id="Config_Button">${literals.pt.li1}</a></li><li>${literals.pt.li2}</li></ol><img src="./icons/${img_name}" alt="${literals.pt.alt}">`;
      }
    } else {
      // default english
      if (browserName === "Edge") {
        literals.en.li2 = "Select (Allow in InPrivate), as shown in the image.";
      }
      if (browserName === "Firefox") {
        // @ts-ignore
        multiLangContainer.innerHTML = `<p>${literals.en.p1}</p><p><a href="#" id="Config_Button">${literals.en.li1}</a></p>`;
      }
      else {
        // @ts-ignore
        multiLangContainer.innerHTML = `<p>${literals.en.p1}</p><ol><li><a href="#" id="Config_Button">${literals.en.li1}</a></li><li>${literals.en.li2}</li></ol><img src="./icons/${img_name}" alt="${literals.en.alt}">`;
      }
    }
  }
  setLiterals();
  // opens a communication between scripts
  // @ts-ignore
  let port = chrome.runtime.connect();
  // listens to the click of the button into the popup content
  // @ts-ignore
  document.getElementById('Config_Button').addEventListener('click', function () {
    // sends a message throw the communication port
    port.postMessage({
      'from': 'popup',
      'start': 'Y'
    });
  });
});
