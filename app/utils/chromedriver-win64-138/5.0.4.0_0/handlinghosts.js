import * as constants from './constants.js';
import * as console from './console.js';
import * as functions from './functions.js';
import * as rtCheck from './RTCheck.js'

export function getContainerIdByUrl(url) {
    console.consoleLogDebug(constants.HandlingHosts, `getContainerIDByUrl - url: ${url}`);
    if (!functions.isNullOrEmpty(url)) {
        return getContainerIdByHost((new URL(url)).host);
    }
    return "";
}

export function getContainerIdByHost(host, checkDomainCoincidence = true) {
    console.consoleLogDebug(constants.HandlingHosts, `getContainerIdByHost - host: ${host}`);
    return getContainerId(host, checkDomainCoincidence);
}


export function getContainerId(host, checkDomainCoincidence) {
    // @ts-ignore
    let element = getHostElement(host, checkDomainCoincidence);
    let containerId= "";
    if (element != null && element != "undefined"){
        containerId = element.containerId;
    }    
    return containerId;
}

export function getProtocolFromUrl (url) {
    console.consoleLogDebug(constants.HandlingHosts, `getProtocolFromUrl - url: ${url} `);
    if (!functions.isNullOrEmpty(url)) {
        return getProtocolByHost((new URL(url)).host);
    }
    return "";
}

export function getProtocolByHost(host) {
    console.consoleLogDebug(constants.HandlingHosts, `getProtocolByHost - host: ${host}`);
    return getProtocol(host, true);
}

function getProtocol(host, checkDomainCoincidence) {
    // @ts-ignore
    let element = getHostElement(host, checkDomainCoincidence);
    let protocol= "";
    if (element != null && element != "undefined"){
        protocol = element.protocol;
    }
    return protocol;
}

function createHandleHostElement(url, containerId, issuer, protocol, triggerEvent, policyId, appGroupId, protocolId) {
    let incognito = isIncognito();
    console.consoleLogDebug(constants.HandlingHosts, `createHandleHostElement - URL: ${url} - containerId: ${containerId} - issuer: ${issuer} - protocol: ${protocol} - incognito: ${incognito}`);
    return { url: url, 
        containerId : containerId, 
        issuer: issuer,
        protocol : protocol,
        incognito: incognito,
        mappedSites : {
            triggerEvent: triggerEvent,
            policyId: policyId,
            appGroupId: appGroupId,
            eventCreated : false},
        protocolIds:[protocolId]
        }; 
    }

export function addUpNewHandledHost(containerId, url, issuer, protocol, protocolId) {
    addUpNewHandledHostWithOrigin(containerId, url, issuer, protocol, false, 0, 0, protocolId);
}

export function addUpNewHandledHostWithOrigin(containerId, url, issuer, protocol, triggerEvent, policyId, appGroupId, protocolId) {
    let incognito = isIncognito();
    console.consoleLogDebug(constants.HandlingHosts, `addUpNewHandledHost - URL: ${url} - containerId: ${containerId} - issuer: ${issuer} - protocol: ${protocol} - incognito: ${incognito}`);
    if (!functions.isNullOrEmpty(containerId) &&
        !functions.isNullOrEmpty(url)) {
        if(!rtCheck.handledHostsList.some(element => element.url == url && element.containerId == containerId && element.incognito == incognito)) {
            console.consoleLogDebug(constants.HandlingHosts, `addUpNewHandledHost push in dict the url ${url} for containerId ${containerId}`);
            rtCheck.handledHostsList.push(createHandleHostElement(url, containerId, issuer, protocol, triggerEvent, policyId, appGroupId, protocolId));

            // Fix for sede.dipucadiz.es issue & sprygt.dipucadiz.es issue.
            if (url == "sso.dipucadiz.es") {
                console.consoleLogForce(constants.HandlingHosts, "Current URL requires to add sede.dipucadiz.es & sprygt.dipucadiz.es as handled URL")
                rtCheck.handledHostsList.push(createHandleHostElement("sede.dipucadiz.es", containerId, issuer, protocol, false, 0, 0, protocolId));
                rtCheck.handledHostsList.push(createHandleHostElement("sprygt.dipucadiz.es", containerId, issuer, protocol, false, 0, 0, protocolId));
            }
        }
        addNewProtocolId(url, protocolId)
    } 
}

export function getIsPreviouslyDeniedUrl(host) {
    let key = rtCheck.generateDictionaryKey(host);
    if (rtCheck.deniedURLDict[key] && rtCheck.deniedURLDict[key].denied == 1) {
        console.consoleLogDebug(constants.HandlingHosts, `URL PREVIOUSLY  Denied cancel navigation. key: {${key}} -  Host : {${host}} - ContainerId : {${rtCheck.deniedURLDict[key].containerId}}`);
        rtCheck.notifyBlockPage(host, constants.NAV_CONTROL, 0, 0, rtCheck.deniedURLDict[key].containerId);
        return true;
    }
    return false;
}

export function isIncognito() { 
    return rtCheck.tabsMode[rtCheck.currentTabId];
}

export function getHostElementByContainerId(host, containerID) {
    console.consoleLogDebug(constants.HandlingHosts, "getAuthHostElement - " + host);
    let elementToReturn = createHandleHostElement(host, "", host, 0);
    elementToReturn = rtCheck.handledHostsList.find(element =>  
        element.containerId === containerID && 
        (element.url === host || functions.calculateSimilarity(host, element.url))
    ) || elementToReturn;

    return elementToReturn;
}

export function getHostElement(host, checkDomainCoincidence) {
    console.consoleLogDebug(constants.HandlingHosts, `getContainerId. host:[${host}] checkDomainCoincidence:${checkDomainCoincidence}`)
    let elementToReturn ;
    try{        
        let incognito = isIncognito();
        console.consoleLogDebug(constants.HandlingHosts, `getContainerId - incognito: ${incognito}`);
        if (!functions.isNullOrEmpty(host)) {
            for (const element of rtCheck.handledHostsList) {
                if (element.incognito === incognito && 
                    (element.url === host || functions.calculateSimilarity(host, element.url) || (checkDomainCoincidence && functions.checkSimilarityBetweenHostnames(host, element.url)))) {
                        elementToReturn = element;
                    break;
                }
            }
        }
    } catch (error) {
        console.consoleLogError(constants.HandlingHosts, "An error ocurred in getHostElement", error);
    }
    return elementToReturn;
}


export function createDeniedHostListElement(containerId, protocol){
    return {denied : 1, containerId: containerId, protocol: protocol, incognito: isIncognito() };
}

export function getUnknowTabIncognitoState(){
     // @ts-ignore
     chrome.tabs.query({ windowId: rtCheck.currentWindowId}, function (tabs) {
        // The tabs variable contains an array of tabs matching the query
        for (const item of tabs){
            if (!rtCheck.tabsMode[item.id]){
                rtCheck.tabsMode[item.id] = item.incognito;
            }
        }        
    });
}

export function addNewProtocolId(host, id)
{
    try
    {
        console.consoleLogDebug(constants.HandlingHosts, `addNewProtocolId. starts. id protocol ${id} to ${host}`);
        let element = getHostElement(host, false);
        if (!element.protocolIds.includes(id) ){
            console.consoleLogDebug(constants.HandlingHosts, `addNewProtocolId. Adding new id protocol`);
            element.protocolIds.push(id);
        }
        else
        {
            console.consoleLogDebug(constants.HandlingHosts, `addNewProtocolId. Already exists`);
        }
        
        if (functions.isURL(element.issuer) && element.issuer != host)
        {
            console.consoleLogDebug(constants.HandlingHosts, `addNewProtocolId. Trying to add to secondary host. ask new url : ${element.issuer}`);
            addNewProtocolId(element.issuer, id)
        }

    } catch (error) {
        console.consoleLogError(constants.HandlingHosts, "An error ocurred in addNewProtocolId", error);
    }
}
