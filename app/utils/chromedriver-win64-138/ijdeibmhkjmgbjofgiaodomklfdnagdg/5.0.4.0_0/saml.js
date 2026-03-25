// @ts-ignore
import * as constants from './constants.js';
import * as console from './console.js';
import * as rtCheck from './RTCheck.js';
import * as handlinghosts from './handlinghosts.js';
import * as functions from './functions.js';
import * as regex from './regex.js';

///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
/////////////////////////            SAML (CLAVE FIRMA)   /////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////

export function checkSAMLAssertion(url, postData,  initiator) {
    if (postData && postData !== "") {
        let samlRequest = postData.includes("SAMLRequest");
        let samlResponse = postData.includes("SAMLResponse");
        if (samlRequest) {
            checkSamlAssertionRequest(url, postData);        
        }
        else if (Object.keys(rtCheck.handledHostsList).length > 0 &&
            Object.keys(rtCheck.authRequestDict).length > 0 &&
            samlResponse) {
                return checkSamlAssertionResponse(url, postData, initiator);
        }
    }
    return samlResult(true, false);;
}

function samlResult(result, policy)
{
    return {result:result, policy:policy}
}

function createauthRequestDictItem(samlId, url, urlIssuer)
{
    console.consoleLogForce(constants.SAML,`Create new authRequestDict element: samlid:[${samlId}] url: [${url}] currenttabid: [${rtCheck.currentTabId}] `);
    let incognito = handlinghosts.isIncognito();    
    console.consoleLogForce(constants.SAML,`Create new authRequestDict element: incognito:[${incognito}]`);
    return { samlId : samlId, url: url, protocol: constants.SAML, incognito: incognito, host: (new URL(urlIssuer)).host, urlHost: urlIssuer };
}

function checkSamlAssertionRequest(url, postDataDecoded) {
    console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLRequest " + url);
    var host = "";
    var elements = getSamlAssertionVariables(postDataDecoded, "AssertionConsumerServiceURL", "AuthnRequest")
    if (elements["AssertionConsumerServiceURL"] != null && elements["ID"] != null) {
        console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLRequest AssertionConsumerServiceURL " + elements["AssertionConsumerServiceURL"] + " ID " + elements["ID"]);
        host = (new URL(elements["AssertionConsumerServiceURL"])).host;
        rtCheck.authRequestDict[rtCheck.generateDictionaryKey(host)] = createauthRequestDictItem(elements["ID"], url, elements["AssertionConsumerServiceURL"]);        

    }
    else
    {
        console.consoleLogForce(constants.SAML, "The saml request doesn't contains the required elements");       
    }
}


function checkSamlAssertionResponse(url, postDataDecoded, initiator) {
    try
    {
        console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLResponse " + url);        

        var elements = getSamlAssertionVariables(postDataDecoded, "InResponseTo", "Response")
        var elementAuthRequest = elements[0]; // it's for initialize the element
        if (elements["Destination"] != null && 
            elements["InResponseTo"] != null &&
            (elements["Consent"] == null ||
            elements["Consent"].includes("consent:obtained"))) {
            var urlDestination = elements["Destination"];
            var inResponseToAssertion = elements["InResponseTo"];
            console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLResponse Destination " + urlDestination + " InResponseTo " + inResponseToAssertion);
            var containerId = handlinghosts.getContainerIdByUrl(url);
            var hostRequestUrl = (new URL(url)).host;
            var hostDestinationtUrl = (new URL(urlDestination)).host;

            let hostUrlKey = rtCheck.generateDictionaryKey(hostRequestUrl);
            let hostUrlDestinationKey = rtCheck.generateDictionaryKey(hostDestinationtUrl);
            elementAuthRequest = rtCheck.authRequestDict[hostUrlKey]
            if (functions.isNullOrEmpty(containerId) || elementAuthRequest || typeof (elementAuthRequest) == "undefined") {   
                console.consoleLogForce(constants.SAML, `checkSAMLAssertion. element was not located. container id is empty ${functions.isNullOrEmpty(containerId)}. elementauthrequest is null ${elementAuthRequest == null}. elementauthrequest is undefined ${ typeof (elementAuthRequest) == "undefined"}. checkSAMLAssertion SAMLResponse looking for ${url} looking for host ${hostRequestUrl}`);
                if (elementAuthRequest === null) // element was not found, looking for it with the destination url
                {
                    console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLResponse empty element looking for coincidence");
                    console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLResponse looking for " + url + " looking for host " + hostDestinationtUrl);                    
                    elementAuthRequest = rtCheck.authRequestDict[hostUrlDestinationKey]; // lookin into de dictionary searching for the destination url host
                }

                if (elementAuthRequest !== null && typeof (elementAuthRequest) !== "undefined") {//element was located                    
                    var origUrl = elementAuthRequest.url;
                    console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLResponse url to process " + origUrl);
                    containerId = handlinghosts.getContainerIdByUrl(origUrl);
                    console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLResponse newurl containerID " + containerId);
                }
                else { // we didn't locate the element still, looking for issuer
                    var issuerEvaluateHost;
                    var issuerToEvaluate = getSamlAssertionIssuer(postDataDecoded);
                    console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLResponse check if issuer is evaluate " + issuerToEvaluate);
                    if (functions.isURL(issuerToEvaluate)){
                        var contanierIssuerId = handlinghosts.getContainerIdByUrl(issuerToEvaluate);

                        if (issuerToEvaluate.includes("http")) {
                            issuerEvaluateHost = (new URL(issuerToEvaluate)).host;
                            issuerToEvaluate = handlinghosts.getHostElementByContainerId(issuerEvaluateHost, contanierIssuerId).issuer
                        }

                        if (!functions.isNullOrEmpty(contanierIssuerId)) {
                            console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLResponse issuer IS authenticated host. Using as element the current url " + url + " origInResponseTo " + inResponseToAssertion);
                            elementAuthRequest = createauthRequestDictItem(inResponseToAssertion, url, issuerToEvaluate); // the issuer was already processed so we don't have the authrequest element. we create it in memory just to process the request
                            containerId = contanierIssuerId;
                        }
                        else {
                            console.consoleLogForce(constants.SAML, "checkSAMLAssertion SAMLResponse issuer IS NOT authenticated host");
                        }
                    }
                    else
                    { 
                        console.consoleLogDebug(constants.SAML,"the saml assertion doesn't has a url as issuer. The original url is as a handling host. it's a secondary process. The Original process was already done");
                        return samlResult(true, true);                       
                    }
                }
            }

            if (!functions.isNullOrEmpty(containerId) &&
                elementAuthRequest.samlId == inResponseToAssertion) {
                console.consoleLogForce(constants.SAML, "A correct process was done. The first url exists correctly");

                var issuer = getSamlAssertionIssuer(postDataDecoded)
                if (issuer.includes("http")) {
                    var issuerHost = (new URL(issuer)).host;
                    issuer = handlinghosts.getHostElementByContainerId(issuerHost, containerId).issuer;
                }

                let hostToProcess = (new URL(urlDestination)).host;
                let protocol = rtCheck.authRequestDict[hostUrlDestinationKey].protocol;
                let samlId = rtCheck.authRequestDict[hostUrlDestinationKey].samlId;
                delete rtCheck.authRequestDict[hostUrlDestinationKey];

                var newelement = false;
                console.consoleLogForce(constants.SAML, "Process " + hostToProcess);
                if (handlinghosts.getContainerIdByHost(hostToProcess, false) == "") {
                    newelement = true;
                    console.consoleLogForce(constants.SAML, "checkSAMLAssertion register new origin");
                    handlinghosts.addUpNewHandledHost(containerId, hostToProcess, issuer, protocol, samlId);                   
                } else {
                    console.consoleLogForce(constants.SAML, "checkSAMLAssertion register new ID application");
                    handlinghosts.addNewProtocolId(hostToProcess, samlId);
                }
                console.consoleLogDebug(constants.SAML, "checkSAMLAssertion check policy");
                var resultPolicy = regex.checkAllowURL(rtCheck.policyDict[containerId], urlDestination);
                
                if (resultPolicy.result) {
                    console.consoleLogDebug(constants.SAML, "checkSAMLAssertion policy retsult ok");
                    if (newelement) {
                        console.consoleLogDebug(constants.SAML, "checkSAMLAssertion policy retsult ok and new origin");
                        rtCheck.notifyNewOrigin(urlDestination, issuer, resultPolicy.policyId, resultPolicy.filterId, containerId);
                    }
                    return samlResult(true, true);
                }
                else {
                    console.consoleLogForce(constants.SAML, "checkSAMLAssertion BLOCKING new origin");
                    rtCheck.notifyBlockPage(urlDestination, issuer, resultPolicy.policyId, resultPolicy.filterId, containerId);
                    return samlResult(false, true);
                }
            }
        }
        else {
            console.consoleLogForce(constants.SAML, `SAMLResponse malformed. checking initiator [${initiator}] `);
            if (elements.length == undefined) {
                if (!functions.isNullOrEmpty(handlinghosts.getContainerIdByHost(initiator))) {
                    console.consoleLogForce(constants.SAML, "Without SAMLResponse but initiator already authorized");
                    return samlResult(true, false);
                }
                else {
                    console.consoleLogForce(constants.SAML, "Without SAMLResponse and initiator NOT Authorized");
                    return samlResult(false, false);
                }
            }
        }
    }
    catch (error) {
        console.consoleLogError(constants.SAML, "CheckSamlAssertionResponse ERROR \n" + error);
    }
    return samlResult(false, false);
}

function getSamlAssertionVariables(postData, localice, item) {
    let samlElements = {};
    try
    {
        var xmlString = "";
        var objcheck = JSON.parse(postData);
        if (objcheck.hasOwnProperty("SAMLRequest")) {
            console.consoleLogDebug(constants.SAML, `GetSamlAssertionVariables postData contains SAMLRequest property`);
            if (objcheck.hasOwnProperty("GetCall")){
                xmlString = objcheck.SAMLRequest;
            }
            else{
                xmlString = atob(objcheck.SAMLRequest);
            }
        }
        else if (objcheck.hasOwnProperty("SAMLResponse")) {
            console.consoleLogDebug(constants.SAML, `GetSamlAssertionVariables postData contains SAMLResponse property`);
            xmlString = atob(objcheck.SAMLResponse);
        }

        if (xmlString.includes(localice)) {
            console.consoleLogDebug(constants.SAML, `String to evaluate includes ${localice} value`);
            //first step
            var regex = /<([^>]+)>/g;
            var matches = xmlString.match(regex);
            // @ts-ignore
            let element = matches.filter(e => e.includes(item))

            //second step
            regex = /(\w+)="([^"]*)"/g;
            var onlyTextVariables = element[0].substring(element[0].indexOf(" ") + 1).slice(0, -1)

            var match;
            while ((match = regex.exec(onlyTextVariables)) !== null) {
                var el1 = match[1];
                var el2 = match[2];
                samlElements[el1] = el2;
            }
        }
    }
    catch (error) {
        console.consoleLogError(constants.SAML, "GetSamlAssertionVariables ERROR \n" + error);
    }
    return samlElements;
}

function getSamlAssertionIssuer(postData) {
    try{
        var xmlString = "";
        var objcheck = JSON.parse(postData);
        if (objcheck.hasOwnProperty("SAMLResponse")) {
            console.consoleLogDebug(constants.SAML, `getSamlAssertionIssuer postData contains SAMLResponse property`);
            xmlString = atob(objcheck.SAMLResponse);
            if (xmlString.includes("saml:Issuer")){
                const regex2 = /<saml:Issuer>(.*?)<\/saml:Issuer>/g;
                
                const match2 = xmlString.match(regex2);
                // @ts-ignore
                return match2[0].replace(/<saml:Issuer>([\s\S]*?)<\/saml:Issuer>/g, '$1');
            }
            else{
                const regex2 = /<saml2:Issuer Format="urn:oasis:names:tc:SAML:2.0:nameid-format:entity">(.*?)<\/saml2:Issuer>/g;
                
                const match2 = xmlString.match(regex2);
                // @ts-ignore
                return match2[0].replace(/<saml2:Issuer Format="urn:oasis:names:tc:SAML:2.0:nameid-format:entity">|<\/saml2:Issuer>/g, "");
            }
        }
    }
    catch (error) {
        console.consoleLogError(constants.SAML, "getSamlAssertionIssuer ERROR \n" + error);
    }
    return "";
}

