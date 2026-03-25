import * as constants from './constants.js';
import * as console from './console.js';
import * as functions from './functions.js';
import * as regex from './regex.js';
import * as handlingHosts from './handlinghosts.js'
import * as rtCheck from './RTCheck.js'


///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
////////////////////////            OPENID (BRAZIL)    ////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////

export function handleOpenId(urlcalled) {
    try {        
        if (urlcalled.hostname === constants.brasilOpenIDCertWeb) {
            if(!checkUrlOpenIdRequest(urlcalled)){
                return openidResult(false, false);
            }
        }
        if (urlcalled.hostname === constants.brasilOpenIDGovWeb) {
            checkUrlOpenId(urlcalled);

            if (Object.keys(rtCheck.openIdAlreadyLogged).length > 0) {
                let result = checkPossibleOpenIDSubAuthorization(urlcalled);
                // @ts-ignore
                if (!result.result) {
                    console.consoleLogForce(constants.OPENID, "Access to url after login. cancel");
                    return result;//OpenId authorization
                }
            }
        }
        return openidResult(true, false);
    }
    catch (error) {
        console.consoleLogError(constants.OPENID, "HandleOpenId ERROR \n" + error);
    }
    return openidResult(false, false);
}

function getNewOpenIdAuxDataArray(urlhost,
    redirecthost,
    responseType,
    scope,
    state,
    alreadyLogged,
    urlhostFullUrl,
    redirecthostFullUrl) {
        
    let incognito = handlingHosts.isIncognito();
    return {
      urlhost :  urlhost,
      redirecthost:  redirecthost,
      responseType:  responseType,
      scope:  scope,
      state:  state,
      OpenIDAuthId: '',
      OpenIDGotAuth:  false,
      OpenIdAuthHost :  '',
      alreadyLogged:  alreadyLogged,
      urlhostFullUrl:  urlhostFullUrl,
      redirecthostFullUrl: redirecthostFullUrl,
      protocol: constants.OPENID,
      incognito: incognito
    };
}

function openidResult(result, policy)
{
    return {result:result, policy:policy}
}

function checkUrlOpenId(url) {
    try {
        if (url.pathname === "/authorize") {
            authorizationProcess(url);
        }
        else if (url.pathname === "/logout") { // User has request to logout, reset all
            logout(url);            
        }
        else if (url.pathname === "/login") {
            loginRequested(url);            
        }
    }
    catch (error) {
        console.consoleLogError(constants.OPENID, "checkUrlOpenId ERROR \n" + error);
    }
}

function authorizationProcess(url)
{
    console.consoleLogForce(constants.OPENID, "Authorization request");
    if (!handlingHosts.getContainerId(constants.brasilOpenIDGovWeb, false)) { // it's first time we get a login request
        firstLogin(url);
    }
    else {   // the url exists already so we got the autentication (certificate using) already
            // and we must check that we get the autorizathion again
        newLogin(url);
    }
}

function firstLogin(url)
{
    let urlredirect;
    console.consoleLogForce(constants.OPENID, "Got authorize. New request");
    let client_id = url.searchParams.get('client_id');
    if (!rtCheck.openIdRelatedDomains.hasOwnProperty(rtCheck.generateDictionaryKey(client_id))) {
        console.consoleLogForce(constants.OPENID, "Got authorize. New request. First step");
        let redirect_uri = url.searchParams.get('redirect_uri');
        if (redirect_uri != null) {
            urlredirect = (new URL(redirect_uri));
        }
        let response_type = url.searchParams.get('response_type');
        let scope = url.searchParams.get('scope');
        let state = url.searchParams.get('state');
        
        rtCheck.openIdRelatedDomains[rtCheck.generateDictionaryKey(client_id)] = getNewOpenIdAuxDataArray(
            url.host,
            // @ts-ignore
            urlredirect.host,
            response_type,
            scope,
            state,
            constants.OPEN_ID_NO_LOGGED,
            url,
            redirect_uri
        );
    }
}


function newLogin(url)
{
    let urlredirect;
    console.consoleLogForce(constants.OPENID, "Got authorize. Already logged. First step.");
    let redirect_uri = url.searchParams.get('redirect_uri');
    if (redirect_uri != null) {
        urlredirect = (new URL(redirect_uri));
    }
    // @ts-ignore
    if (handlingHosts.getContainerId(urlredirect.host, false)) {
        // this host was already authorized, nothing to do
        return;
    }
    let response_type = url.searchParams.get('response_type');
    let scope = url.searchParams.get('scope');
    let state = url.searchParams.get('state');
    // in this point we use state as a key bacause we don't have another possible key in this second login time
    rtCheck.openIdAlreadyLogged[rtCheck.generateDictionaryKey(state)] = getNewOpenIdAuxDataArray(
        url.host,
        // @ts-ignore
        urlredirect.host,
        response_type,
        scope,
        state,
        constants.OPEN_ID_LOGGED,
        url,
        redirect_uri
    );
}

function logout(url){
    console.consoleLogForce(constants.OPENID, "Got logout");
    if (url.searchParams.get('post_logout_redirect_uri') != null) {
        rtCheck.clearDictionarys(constants.OPENID)
    }
}

function loginRequested(url){
    console.consoleLogForce(constants.OPENID, "Got Login. New request. second step");
    let client_id = url.searchParams.get('client_id');
    let authorization_id = url.searchParams.get('authorization_id');
    let key = rtCheck.generateDictionaryKey(client_id);
    if (rtCheck.openIdRelatedDomains.hasOwnProperty(key)) {
        rtCheck.openIdRelatedDomains[key].OpenIDAuthId = authorization_id;
    }
}

function checkUrlOpenIdRequest(url) {
    try {
        console.consoleLogForce(constants.OPENID, "Got auth page.");
        if (url.pathname === "/login") {
            console.consoleLogForce(constants.OPENID, "Got auth page. Login.");
            let client_id = url.searchParams.get('client_id');
            let authorization_id = url.searchParams.get('authorization_id');
            let key = rtCheck.generateDictionaryKey(client_id);
            if (rtCheck.openIdRelatedDomains.hasOwnProperty(key)) {
                console.consoleLogForce(constants.OPENID, "Got auth page. Login. third step");
                if (rtCheck.openIdRelatedDomains[key].OpenIDAuthId == authorization_id) {
                    rtCheck.openIdRelatedDomains[key].OpenIDGotAuth = true;
                    rtCheck.openIdRelatedDomains[key].OpenIdAuthHost = url.host;
                }                
            }
            else {
                if (!handlingHosts.getContainerId(url.host, false)) {
                    console.consoleLogError(constants.OPENID, "Got auth page. TAMPER");
                    // We are getting a request to login and we don't have the previous steps.
                    // All navigation is cancelled
                    return false;
                }
            }
        }
    }
    catch (error) {
        console.consoleLogError(constants.OPENID, "checkUrlOpenIdRequest ERROR \n" + error);
        return false;      
    }
    return true;
}

function checkPossibleOpenIDSubAuthorization(urlcalled) {
    let result = openidResult(true, false);
    let surl;
    let state = urlcalled.searchParams.get('state');
    
    if (state != null) {
        console.consoleLogForce(constants.OPENID, "got state.." + state + "[" + urlcalled.host + "]");
        let key = rtCheck.generateDictionaryKey(state)
        if (rtCheck.openIdAlreadyLogged.hasOwnProperty(key)) {
            let item = rtCheck.openIdAlreadyLogged[key];
            console.consoleLogForce(constants.OPENID, "Got authorize. Already logged. Second step.");
            if (item.alreadyLogged == constants.OPEN_ID_LOGGED) {
                let containerId = handlingHosts.getContainerId(item.urlhost, false)
                if (!functions.isNullOrEmpty(containerId)) {
                    let shost = item.redirecthost;
                    surl = item.redirecthostFullUrl;
                    let resultPolicy = regex.checkAllowURL(rtCheck.policyDict[containerId], surl);
                    handlingHosts.addUpNewHandledHost(containerId, shost, constants.OPENID, constants.OPENID, constants.OPENID); 
                    if (!resultPolicy.result) {
                        console.consoleLogForce(constants.OPENID, `Blocked by policy : host [${shost}], policyId [${resultPolicy.policyId}], filterId [${resultPolicy.filterId}], containerID [${containerId}]`);
                        rtCheck.deniedURLDict[rtCheck.generateDictionaryKey(shost)] = handlingHosts.createDeniedHostListElement(containerId, constants.OPENID);
                        rtCheck.notifyBlockPage(surl, constants.brasilGateway, resultPolicy.policyId, resultPolicy.filterId, containerId);
                        result = openidResult(false, true);
                    }
                    else {
                        rtCheck.notifyNewOrigin(surl, constants.brasilGateway, resultPolicy.policyId, resultPolicy.filterId, containerId);
                        result = openidResult(true, true);
                    }
                    delete rtCheck.openIdAlreadyLogged[key];
                }
            }
        }
    }
    else {
        result = {result:true, policy:false};
        const entries = Object.entries(rtCheck.openIdAlreadyLogged);
        for (const [index, element] of entries) {
            if (element.OpenIDRedirectHost == urlcalled.host &&
                element.alreadyLogged == constants.OPEN_ID_LOGGED) {
                let containerId = handlingHosts.getContainerId(urlcalled.host, false)
                console.consoleLogForce(constants.OPENID, "Got authorize. Already logged. deleted.");
                rtCheck.deniedURLDict[rtCheck.generateDictionaryKey(urlcalled.host)] = handlingHosts.createDeniedHostListElement(containerId, constants.OPENID);
                rtCheck.setTamper();
                delete rtCheck.openIdAlreadyLogged[index];
                result = openidResult(false, false);
            }
        }
    }
    return result;
   
}

export function AuthorizeOpenIdPath(containerId, host){
    const entries = Object.entries(rtCheck.openIdRelatedDomains);
    console.consoleLogForce(constants.OPENID, "AuthorizeOpenIdPath. entries." + entries.length);
    let incognito = handlingHosts.isIncognito();
    
    for (const [index, element] of entries) {
        console.consoleLogForce(constants.OPENID, "AuthorizeOpenIdPath. index." + index);
        if (element.OpenIdAuthHost == host &&
            element.OpenIDGotAuth  &&
            element.protocol == constants.OPENID &&
            element.incognito == incognito) {
            console.consoleLogForce(constants.OPENID, `Got authorize. New request. Last step after policy. Got handling host : [${element.urlhost}] url :  [${element.redirecthostFullUrl}]`);
            handlingHosts.addUpNewHandledHost(containerId, element.urlhost, constants.brasilGateway, constants.OPENID, constants.OPENID);
            let redirectorhost = (new URL(element.redirecthostFullUrl)).host;
            handlingHosts.addUpNewHandledHost(containerId, redirectorhost, constants.brasilGateway, constants.OPENID, constants.OPENID);

            let resultPolicy = regex.checkAllowURL(rtCheck.policyDict[containerId], element.urlhostFullUrl.href);
            if (resultPolicy.result) {
                console.consoleLogForce(constants.OPENID, `AuthorizeOpenIdPath. notifyNewOrigin`);
                rtCheck.notifyNewOrigin(element.urlhostFullUrl, constants.brasilGateway, resultPolicy.policyId, resultPolicy.filterId, containerId);
            }
            else {                
                console.consoleLogForce(constants.OPENID, `Blocked by policy (1): host [${element.urlhostFullUrl}], policyId [${resultPolicy.policyId}], filterId [${resultPolicy.filterId}], containerID [${containerId}]`);
                rtCheck.deniedURLDict[rtCheck.generateDictionaryKey((new URL(element.urlhost).host))] = handlingHosts.createDeniedHostListElement(containerId, constants.OPENID);
                rtCheck.notifyBlockPage(element.urlhostFullUrl, constants.brasilGateway, resultPolicy.policyId, resultPolicy.filterId, containerId);
                return false;
            }
            resultPolicy = regex.checkAllowURL(rtCheck.policyDict[containerId], element.redirecthostFullUrl);
            if (resultPolicy.result) {
                delete rtCheck.openIdRelatedDomains[index];
                rtCheck.notifyNewOrigin(element.redirecthostFullUrl, constants.brasilGateway, resultPolicy.policyId, resultPolicy.filterId, containerId);
                return true;
            }
            else {
                console.consoleLogForce(constants.OPENID, `Blocked by policy (2): host [${element.redirecthostFullUrl}], policyId [${resultPolicy.policyId}], filterId [${resultPolicy.filterId}], containerID [${containerId}]`);
                delete rtCheck.openIdRelatedDomains[index];
                rtCheck.deniedURLDict[rtCheck.generateDictionaryKey((new URL(element.redirecthostFullUrl).host))] = handlingHosts.createDeniedHostListElement(containerId, constants.OPENID);
                rtCheck.notifyBlockPage(element.redirecthostFullUrl, constants.brasilGateway, resultPolicy.policyId, resultPolicy.filterId, containerId);
                return false;
            }
        }
    }
    console.consoleLogError(constants.OPENID, "Authorization ERROR.");
    return false;
   
}
