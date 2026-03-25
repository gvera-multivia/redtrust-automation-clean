// always waits the document to be loaded when shown
document.addEventListener('DOMContentLoaded', function () {
  let literals = {
    es: {
      TAMPER: {
        msg: "Ha ocurrido un problema con el control de la navegación. Para continuar, es necesario reiniciar completamente el navegador y,  si el problema persiste, por favor, póngase en contacto con su administrador de Redtrust. Código de error: <b class='text-error'>TAMPER</b>",
        btn: "Volver"
      },
      WRONG_OPENID: {
        msg: "Ha ocurrido un problema con el control de la navegación o con la aplicación de las políticas. Para continuar, reintente la operación y, si el problema persiste, por favor, póngase en contacto con su administrador de Redtrust. Código de error: <b class='text-error'>ERR_OPENID</b>",
        btn: "Volver"
      },
      WRONG_SAML_AUTH: {
        msg: "Ha ocurrido un problema con el control de la navegación o con la aplicación de las políticas. Para continuar, reintente la operación y, si el problema persiste, por favor, póngase en contacto con su administrador de Redtrust. Código de error: <b class='text-error'>ERR_SAML</b>",
        btn: "Volver"
      },
      POLICIES_PROCESS: {
        msg: "Ha ocurrido un problema con el control de la navegación o con la aplicación de las políticas. Para continuar, reintente la operación y, si el problema persiste, por favor, póngase en contacto con su administrador de Redtrust. Código de error: <b class='text-error'>POLICIES_PROCESS</b>",
        btn: "Volver"
      },
      POLICY_SYSTEM_EXCEPTION: {
        msg: "Ha ocurrido un problema con el control de la navegación o con la aplicación de las políticas. Para continuar, reintente la operación y, si el problema persiste, por favor, póngase en contacto con su administrador de Redtrust. Código de error: <b class='text-error'>POLICY_SYSTEM_EXCEPTION</b>",
        btn: "Volver"
      },
      SYSTEM_EXCEPTION: {
        msg: "Ha ocurrido un problema con el control de la navegación o con la aplicación de las políticas. Para continuar, reintente la operación y, si el problema persiste, por favor, póngase en contacto con su administrador de Redtrust. Código de error: <b class='text-error'>SYSTEM_EXCEPTION</b>",
        btn: "Volver"
      },
      POLICIES_PROCESS_EMPTY: {
        msg: "Ha ocurrido un problema con el control de la navegación o con la aplicación de las políticas. Para continuar, reintente la operación y, si el problema persiste, por favor, póngase en contacto con su administrador de Redtrust. Código de error: <b class='text-error'>POLICIES_PROCESS_EMPTY</b>",
        btn: "Volver"
      }
    },
    ca: {
      TAMPER: {
        msg: "S'ha produït un problema amb el control de navegació. Per continuar, cal reiniciar completament el navegador i, si el problema persisteix, si us plau, poseu-vos en contacte amb el vostre administrador de Redtrust. Codi d'error: <b class='text-error'>TAMPER</b>",
        btn: "Tornar"
      },
      WRONG_OPENID: {
          msg: "S'ha produït un problema amb el control de la navegació o amb l'aplicació de les polítiques. Per continuar, reintenteu l'operació i, si el problema persisteix, si us plau, poseu-vos en contacte amb el vostre administrador de Redtrust. Codi d'error: <b class='text-error'>ERR_OPENID</b>",
          btn: "Tornar"
      },
      WRONG_SAML_AUTH: {
          msg: "S'ha produït un problema amb el control de la navegació o amb l'aplicació de les polítiques. Per continuar, reintenteu l'operació i, si el problema persisteix, si us plau, poseu-vos en contacte amb el vostre administrador de Redtrust. Codi d'error: <b class='text-error'>ERR_SAML</b>",
          btn: "Tornar"
      },
      POLICIES_PROCESS: {
          msg: "S'ha produït un problema amb el control de la navegació o amb l'aplicació de les polítiques. Per continuar, reintenteu l'operació i, si el problema persisteix, si us plau, poseu-vos en contacte amb el vostre administrador de Redtrust. Codi d'error: <b class='text-error'>POLICIES_PROCESS</b>",
          btn: "Tornar"
      },
      POLICY_SYSTEM_EXCEPTION: {
          msg: "S'ha produït un problema amb el control de la navegació o amb l'aplicació de les polítiques. Per continuar, reintenteu l'operació i, si el problema persisteix, si us plau, poseu-vos en contacte amb el vostre administrador de Redtrust. Codi d'error: <b class='text-error'>POLICY_SYSTEM_EXCEPTION</b>",
          btn: "Tornar"
      },
      SYSTEM_EXCEPTION: {
          msg: "S'ha produït un problema amb el control de la navegació o amb l'aplicació de les polítiques. Per continuar, reintenteu l'operació i, si el problema persisteix, si us plau, poseu-vos en contacte amb el vostre administrador de Redtrust. Codi d'error: <b class='text-error'>SYSTEM_EXCEPTION</b>",
          btn: "Tornar"
      },
      POLICIES_PROCESS_EMPTY: {
          msg: "S'ha produït un problema amb el control de la navegació o amb l'aplicació de les polítiques. Per continuar, reintenteu l'operació i, si el problema persisteix, si us plau, poseu-vos en contacte amb el vostre administrador de Redtrust. Codi d'error: <b class='text-error'>POLICIES_PROCESS_EMPTY</b>",
          btn: "Tornar"
      }
    },
    pt: {
      TAMPER: {
        msg: "Ocorreu um problema com o controle de navegação. Para continuar, é necessário reiniciar completamente o navegador e, se o problema persistir, entre em contato com o administrador da Redtrust. Código de erro: <b class='text-error'>TAMPER</b>",
        btn: "Voltar"
      },
      WRONG_OPENID: {
          msg: "Ocorreu um problema com o controle de navegação ou a aplicação de políticas. Para continuar, tente novamente a operação e, se o problema persistir, entre em contato com o administrador da Redtrust. Código de erro: <b class='text-error'>ERR_OPENID</b>",
          btn: "Voltar"
      },
      WRONG_SAML_AUTH: {
          msg: "Ocorreu um problema com o controle de navegação ou a aplicação de políticas. Para continuar, tente novamente a operação e, se o problema persistir, entre em contato com o administrador da Redtrust. Código de erro: <b class='text-error'>ERR_SAML</b>",
          btn: "Voltar"
      },
      POLICIES_PROCESS: {
          msg: "Ocorreu um problema com o controle de navegação ou a aplicação de políticas. Para continuar, tente novamente a operação e, se o problema persistir, entre em contato com o administrador da Redtrust. Código de erro: <b class='text-error'>POLICIES_PROCESS</b>",
          btn: "Voltar"
      },
      POLICY_SYSTEM_EXCEPTION: {
          msg: "Ocorreu um problema com o controle de navegação ou a aplicação de políticas. Para continuar, tente novamente a operação e, se o problema persistir, entre em contato com o administrador da Redtrust. Código de erro: <b class='text-error'>POLICY_SYSTEM_EXCEPTION</b>",
          btn: "Voltar"
      },
      SYSTEM_EXCEPTION: {
          msg: "Ocorreu um problema com o controle de navegação ou a aplicação de políticas. Para continuar, tente novamente a operação e, se o problema persistir, entre em contato com o administrador da Redtrust. Código de erro: <b class='text-error'>SYSTEM_EXCEPTION</b>",
          btn: "Voltar"
      },
      POLICIES_PROCESS_EMPTY: {
          msg: "Ocorreu um problema com o controle de navegação ou a aplicação de políticas. Para continuar, tente novamente a operação e, se o problema persistir, entre em contato com o administrador da Redtrust. Código de erro: <b class='text-error'>POLICIES_PROCESS_EMPTY</b>",
          btn: "Voltar"
      }
    },
    en: {
      TAMPER: {
        msg: "A problem has occurred with navigation control. To continue, you need to completely restart the browser and if the problem persists, please contact your Redtrust administrator. Error code: <b class='text-error'>TAMPER</b>",
        btn: "Return"
      },
      WRONG_OPENID: {
          msg: "A problem has occurred with navigation control or policy enforcement. To continue, retry the operation and if the problem persists, please contact your Redtrust administrator. Error code: <b class='text-error'>ERR_OPENID</b>",
          btn: "Return"
      },
      WRONG_SAML_AUTH: {
          msg: "A problem has occurred with navigation control or policy enforcement. To continue, retry the operation and if the problem persists, please contact your Redtrust administrator. Error code: <b class='text-error'>ERR_SAML</b>",
          btn: "Return"
      },
      POLICIES_PROCESS: {
          msg: "A problem has occurred with navigation control or policy enforcement. To continue, retry the operation and if the problem persists, please contact your Redtrust administrator. Error code: <b class='text-error'>POLICIES_PROCESS</b>",
          btn: "Return"
      },
      POLICY_SYSTEM_EXCEPTION: {
          msg: "A problem has occurred with navigation control or policy enforcement. To continue, retry the operation and if the problem persists, please contact your Redtrust administrator. Error code: <b class='text-error'>POLICY_SYSTEM_EXCEPTION</b>",
          btn: "Return"
      },
      SYSTEM_EXCEPTION: {
          msg: "A problem has occurred with navigation control or policy enforcement. To continue, retry the operation and if the problem persists, please contact your Redtrust administrator. Error code: <b class='text-error'>SYSTEM_EXCEPTION</b>",
          btn: "Return"
      },
      POLICIES_PROCESS_EMPTY: {
          msg: "A problem has occurred with navigation control or policy enforcement. To continue, retry the operation and if the problem persists, please contact your Redtrust administrator. Error code: <b class='text-error'>POLICIES_PROCESS_EMPTY</b>",
          btn: "Return"
      }
    }
  }

  function setLiterals() {
    const queryString = window.location.search
    const urlParams = new URLSearchParams(queryString);
    let param = urlParams.get('reason');
    var redirect = document.getElementById("redirect");
    var get_back = document.getElementById("get_back");
    // @ts-ignore
    var userLang = navigator.language || navigator.userLanguage;
    var lang = userLang.substring(0, 2).toLowerCase();
    var msg = "";
    var btn = ""

    switch (param) {
      case 'TAMPER': {
        if (lang === "es") {
          // Español
          msg = literals.es.TAMPER.msg;
          btn = literals.es.TAMPER.btn;
        } else if (lang === "ca") {
          // Catalan
          msg = literals.ca.TAMPER.msg;
          btn = literals.ca.TAMPER.btn;
        } else if (lang === "pt") {
          // Portugues
          msg = literals.pt.TAMPER.msg;
          btn = literals.pt.TAMPER.btn;
        } else {
          // Default English
          msg = literals.en.TAMPER.msg;
          btn = literals.en.TAMPER.btn;
        }
      }
        break;
      case 'WRONG_OPENID': {
        if (lang === "es") {
          // Español
          msg = literals.es.WRONG_OPENID.msg;
          btn = literals.es.WRONG_OPENID.btn;
        } else if (lang === "ca") {
          // Catalan
          msg = literals.ca.WRONG_OPENID.msg;
          btn = literals.ca.WRONG_OPENID.btn;

        } else if (lang === "pt") {
          // Portugues
          msg = literals.pt.WRONG_OPENID.msg;
          btn = literals.pt.WRONG_OPENID.btn;
        } else {
          // Default English
          msg = literals.en.WRONG_OPENID.msg;
          btn = literals.en.WRONG_OPENID.btn;
        }
      }
        break;
      case 'WRONG_SAML_AUTH': {
        if (lang === "es") {
          // Español
          msg = literals.es.WRONG_SAML_AUTH.msg;
          btn = literals.es.WRONG_SAML_AUTH.btn;
        } else if (lang === "ca") {
          // Catalan
          msg = literals.ca.WRONG_SAML_AUTH.msg;
          btn = literals.ca.WRONG_SAML_AUTH.btn;

        } else if (lang === "pt") {
          // Portugues
          msg = literals.pt.WRONG_SAML_AUTH.msg;
          btn = literals.pt.WRONG_SAML_AUTH.btn;
        } else {
          // Default English
          msg = literals.en.WRONG_SAML_AUTH.msg;
          btn = literals.en.WRONG_SAML_AUTH.btn;
        }
      }
        break;
      case 'POLICIES_PROCESS': {
        if (lang === "es") {
          // Español
          msg = literals.es.POLICIES_PROCESS.msg;
          btn = literals.es.POLICIES_PROCESS.btn;
        } else if (lang === "ca") {
          // Catalan
          msg = literals.ca.POLICIES_PROCESS.msg;
          btn = literals.ca.POLICIES_PROCESS.btn;

        } else if (lang === "pt") {
          // Portugues
          msg = literals.pt.POLICIES_PROCESS.msg;
          btn = literals.pt.POLICIES_PROCESS.btn;
        } else {
          // Default English
          msg = literals.en.POLICIES_PROCESS.msg;
          btn = literals.en.POLICIES_PROCESS.btn;
        }
      }
        break;
      case 'POLICY_SYSTEM_EXCEPTION': {
        if (lang === "es") {
          // Español
          msg = literals.es.POLICY_SYSTEM_EXCEPTION.msg;
          btn = literals.es.POLICY_SYSTEM_EXCEPTION.btn;
        } else if (lang === "ca") {
          // Catalan
          msg = literals.ca.POLICY_SYSTEM_EXCEPTION.msg;
          btn = literals.ca.POLICY_SYSTEM_EXCEPTION.btn;

        } else if (lang === "pt") {
          // Portugues
          msg = literals.pt.POLICY_SYSTEM_EXCEPTION.msg;
          btn = literals.pt.POLICY_SYSTEM_EXCEPTION.btn;
        } else {
          // Default English
          msg = literals.en.POLICY_SYSTEM_EXCEPTION.msg;
          btn = literals.en.POLICY_SYSTEM_EXCEPTION.btn;
        }
      }
        break;
      case 'SYSTEM_EXCEPTION': {
        if (lang === "es") {
          // Español
          msg = literals.es.SYSTEM_EXCEPTION.msg;
          btn = literals.es.SYSTEM_EXCEPTION.btn;
        } else if (lang === "ca") {
          // Catalan
          msg = literals.ca.SYSTEM_EXCEPTION.msg;
          btn = literals.ca.SYSTEM_EXCEPTION.btn;

        } else if (lang === "pt") {
          // Portugues
          msg = literals.pt.SYSTEM_EXCEPTION.msg;
          btn = literals.pt.SYSTEM_EXCEPTION.btn;
        } else {
          // Default English
          msg = literals.en.SYSTEM_EXCEPTION.msg;
          btn = literals.en.SYSTEM_EXCEPTION.btn;
        }
      }
        break;
      case 'POLICIES_PROCESS_EMPTY': {
        if (lang === "es") {
          // Español
          msg = literals.es.POLICIES_PROCESS_EMPTY.msg;
          btn = literals.es.POLICIES_PROCESS_EMPTY.btn;
        } else if (lang === "ca") {
          // Catalan
          msg = literals.ca.POLICIES_PROCESS_EMPTY.msg;
          btn = literals.ca.POLICIES_PROCESS_EMPTY.btn;

        } else if (lang === "pt") {
          // Portugues
          msg = literals.pt.POLICIES_PROCESS_EMPTY.msg;
          btn = literals.pt.POLICIES_PROCESS_EMPTY.btn;
        } else {
          // Default English
          msg = literals.en.POLICIES_PROCESS_EMPTY.msg;
          btn = literals.en.POLICIES_PROCESS_EMPTY.btn;
        }
      }
        break;
    }
// @ts-ignore
    redirect.innerHTML =
        `<p class='box-details'>${msg}</p>`;
        // @ts-ignore
    get_back.innerHTML =
        `<button id='historyBack' class='box-action'>
          <img class='icon-back' alt='back' src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGhlaWdodD0iMjRweCIgdmlld0JveD0iMCAwIDI0IDI0IiB3aWR0aD0iMjRweCIgZmlsbD0iIzAwMDAwMCI+PHBhdGggZD0iTTAgMGgyNHYyNEgweiIgZmlsbD0ibm9uZSIvPjxwYXRoIGQ9Ik0yMCAxMUg3LjgzbDUuNTktNS41OUwxMiA0bC04IDggOCA4IDEuNDEtMS40MUw3LjgzIDEzSDIwdi0yeiIvPjwvc3ZnPg==' />
          <span class="btn-label">${btn}</span>
        </button>`;

  }

  setLiterals();
  // FOR navigation back
  // @ts-ignore
  document.getElementById('historyBack').addEventListener('click', function () {
    window.history.back();
  });
});
