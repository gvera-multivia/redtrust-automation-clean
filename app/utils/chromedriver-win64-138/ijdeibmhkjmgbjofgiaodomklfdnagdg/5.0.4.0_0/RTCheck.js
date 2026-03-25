import * as constants from './constants.js';
import * as console from './console.js';
import * as functions from './functions.js';
import * as regex from './regex.js';
import * as handlinghosts from './handlinghosts.js';
import * as saml from './saml.js';
import * as openId from './openId.js';

// @ts-ignore
import {
    setCurrentVersion
} from './functions.js'

//********************************************************/
// Members
//********************************************************/

export let currentWindowId = 0;
export let currentTabId = 0;

let tabURLDict = {}; //Keep a dictionary that contains the tab ids and the current URL of this tab.

export var handledHostsList = [];//Keep a dictionary that contains the url's that where authorized already
export let deniedURLDict = {};//Keep a dictionary that contains the url's that where rejected already
export let policyDict = {};//Keep a dictionary that contains the policies by containerid
export let openIdRelatedDomains = {};//Keep a dictionary that contains related domains for protocol OPENID
export let openIdAlreadyLogged = {};//Keep a dictionary that contains related domains for protocol OPENID already logged
export let authRequestDict = {};//Keep a dictionary that contains the external auth request by saml2
export let tabsMode = {};//Keep a dictionary that contains the external auth request by saml2

export let commChannel = null;
export let suspended = false;
export let blockByTamper = false;
export let blockByWrongPoliciesProcessEmpty = false;
export let blockByWrongPoliciesProcessException = false;
export let beforeRedirectBlocking = false;
export let cancelCurrentNavigation = false;

export let certificateWasRequested = false;

let isAllowedIncognitoAccess = false;
let isEnabledIncognitoAccessBrowserPolicy = true;

/**********************************************************************************/
/**********************************************************************************/
/////////////////////////               CODE        ///////////////////////////////
/**********************************************************************************/
/**********************************************************************************/

function setExtensionVersion(message) {
    console.consoleLogDebug(constants.INITIALIZING, `SetExtensionVersion : ${JSON.stringify(message)}`);
    functions.setCurrentVersion(message.extensionVersion);
    SetIncognitoModeAvailability(message);
    console.SetLogLevel(message);
    postMessage(message);
}

function SetIncognitoModeAvailability(message) {
    console.consoleLogDebug(constants.INITIALIZING, "SetIncognitoModeAvailability begin");
    if (message && "refuseControlOnIncognito" in message && message.refuseControlOnIncognito == true) {
        isAllowedIncognitoAccess = true;
        console.consoleLogForce(constants.INITIALIZING, "Refuse control on incognito");
    }
    // @ts-ignore
    else if (constants.originName == "chrome" && message && "incognitoModeAvailabilityCH" in message) {
        isEnabledIncognitoAccessBrowserPolicy = message.incognitoModeAvailabilityCH;
        console.consoleLogForce(constants.INITIALIZING, "Set IncognitoAccessBrowserPolicy from Chrome policy");
    // @ts-ignore
    } else if (constants.originName == "msedge" && message && "incognitoModeAvailabilityED" in message) {
        isEnabledIncognitoAccessBrowserPolicy = message.incognitoModeAvailabilityED;
        console.consoleLogForce(constants.INITIALIZING, "Set IncognitoAccessBrowserPolicy from Edge policy");
    // @ts-ignore
    } else if (constants.originName == "firefox" && message && "incognitoModeAvailabilityFF" in message) {
        isEnabledIncognitoAccessBrowserPolicy = message.incognitoModeAvailabilityFF;
        console.consoleLogForce(constants.INITIALIZING, "Set IncognitoAccessBrowserPolicy from Firefox policy");
    }
    else {
        console.consoleLogForce(constants.INITIALIZING, "Set IncognitoAccessBrowserPolicy wasn't defined on message");
    }

    if(!isEnabledIncognitoAccessBrowserPolicy) {
        console.consoleLogForce(constants.INITIALIZING, "Call to update status in SetIsAllowedIncognitoAccess");
        setIsAllowedIncognitoAccess();
    }
    console.consoleLogDebug(constants.INITIALIZING, "SetIncognitoModeAvailability end");
}

///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
/////////////////////////            INITIALIZING   ///////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
function startListener() {

    if (!commChannel) {
        console.consoleLogForce(constants.COMM, "Initialize comm");
        // @ts-ignore
        commChannel = chrome.runtime.connectNative("com.redtrust.monitorhost." + constants.originName);
    }
// @ts-ignore
    commChannel.onMessage.addListener(onNativeMessage);
// @ts-ignore
    commChannel.onDisconnect.addListener(onPortDisconnect);

    //Send package to init mesage to configure the RTMonitorHost properly.
    postMessage({ "messageType": "init", "browserType": constants.originName, "extensionId": functions.getExtensionId() });
}

function setIsAllowedIncognitoAccess() {
    console.consoleLogDebug(constants.INITIALIZING, "SetIsAllowedIncognitoAccess");
    try {

        if (!isEnabledIncognitoAccessBrowserPolicy) {
            console.consoleLogForce(constants.INITIALIZING, "Setted isAllowedIncognitoAccess as true value because exists a rule specified in system that disabled incognite navigation")
            isAllowedIncognitoAccess = true;
        }
        else {
            let nav;
            // @ts-ignore
            if (constants.originName == "firefox") {
                // @ts-ignore
                nav = browser;
            }
            else {
                // @ts-ignore
                nav = chrome;
            }

            nav.extension.isAllowedIncognitoAccess().then((isAllowed) => {
                isAllowedIncognitoAccess = isAllowed;
            });
        }

    } catch (error) {
        console.consoleLogError(constants.INITIALIZING, "An error ocurred in SetIsAllowedIncognitoAccess", getErrorMessage(error));
    }

}

function initialize() {
    console.consoleLogForce(constants.INITIALIZING, "Initializing extension : " + constants.originName);
    // @ts-ignore
    if (constants.originName == "firefox") {
        // @ts-ignore
        let gettingInfo = browser.runtime.getBrowserInfo(); //Configure firefox to add module
        // @ts-ignore
        gettingInfo.then(gotBrowserInfo);
    }
    startListener();
    setIsAllowedIncognitoAccess();
}
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
/////////////////////////          COMMUNICATION    ///////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////

function onNativeMessage(message)  {
    console.consoleLogDebug(constants.COMM, "Received message : " + JSON.stringify(message));
    checkReceivedMessages(message);
};

function onPortDisconnect(portHost) {
    console.consoleLogForce(constants.COMM, "Native connnection disconnection event.");
    if (portHost.error) {
        console.consoleLogError(constants.COMM, "Disconnected due to an error", portHost.error.message);
    } else {
        if (suspended) {
            console.consoleLogError(constants.COMM, "Disconnected from the native messaging host.");
        }
        else {
            console.consoleLogError(constants.COMM, "Unexpected disconnection from the native messaging host.");
        }
    }
    commChannel = null; // Clear the reference to the closed commChannel
    console.consoleLogError(constants.COMM, "The communication was lost.");
};

// @ts-ignore
function postMessage(message, retry = true) {
    console.consoleLogDebug(constants.COMM, "Sending native message");
    if (!functions.isNullOrEmpty(message)){
        console.consoleLogForce(constants.COMM, "Message : " + JSON.stringify(message));
        try {
            if (!commChannel) {
                startListener();
            }
            // @ts-ignore
            commChannel.postMessage(message);
        } catch (error) {
            console.consoleLogError(constants.COMM, "An error ocurred posting a message", getErrorMessage(error));
        }
    }
}

// @ts-ignore
function currentUrlProcess(message){
        console.consoleLogDebug(constants.NAV_REQUEST, "Obtain currentUrl");
        if (isAllowedIncognitoAccess) {
            getCurrentTabURL(function (url) {
                let newMessage = { "messageType": "currentUrl", "url": url };
                postMessage(newMessage);
            });
        }
        else {
            notifyIncognitoNotAllowed();
        }
}

// @ts-ignore
function SetRemoteAuthMappedSites(message){
    console.consoleLogDebug(constants.HandlingHosts, `Set remote mapped sites. ContainerId:[${message.containerID}]. policyId:[${message.policyId}]`);
    let hostslist = JSON.parse(message.mappedSitesListFeature);
    for (let host of hostslist)
    {
        host = atob(host);
        if (functions.isNullOrEmpty(handlinghosts.getContainerId(host)))
        {
            console.consoleLogDebug(constants.HandlingHosts, `Including site : [${host}]`);
            handlinghosts.addUpNewHandledHostWithOrigin(message.containerID, host, host, "", true, message.policyId, message.appGroupId, constants.PROTOCOL_MAPPED);
        }
    }

    processRawReceivedPolicies(message);

    console.consoleLogDebug(constants.HandlingHosts, `answer to include hosts`);
    let newMessage = { "messageType": "mappedSitesListFeature"};
    postMessage(newMessage);
}

function checkReceivedMessages(message) {
    switch (message.messageType) {
        case "policies":
            let first = processRawReceivedPolicies(message);
            processAfterReceivedPolicies(first, message);
            break;
        case "setExtensionVersion":
            setExtensionVersion(message);
            break;
        case "currentUrl":
            currentUrlProcess(message);
            break;
        case "mappedSitesListFeature":
            SetRemoteAuthMappedSites(message);
            break;
        default:
            console.consoleLogError(constants.COMM, `Unknow message : [${JSON.stringify(message)}]`);
            break;
    }
}

function notifyIncognitoNotAllowed()
{
    console.consoleLogForce(constants.NAV_CONTROL, "INCOGNITO : Extension must be allowed to read in incognito mode");
    // @ts-ignore
    if (chrome.runtime.openOptionsPage) {
        // @ts-ignore
        chrome.runtime.openOptionsPage();
    } else {
        // @ts-ignore
        window.open(chrome.runtime.getURL('./options/options.html'));
    }
}


function getCurrentTabURL(callBack) {
    console.consoleLogDebug(constants.NAV_CONTROL, "getCurrentTabURL ");
    // @ts-ignore
    chrome.tabs.query({ windowId: currentWindowId }, function (tabs) {
        // The tabs variable contains an array of tabs matching the query
        if (tabs.length > 0) {
            let currentTab = tabs.find(tab => tab.active === true && tab.windowId === currentWindowId);
            if (currentTab) {
                console.consoleLogForce(constants.NAV_CONTROL, `getCurrentTabURL : Current windowId: ${currentTab.windowId}, current tabId: ${currentTab.id}, Title: ${currentTab.title}, URL: ${currentTab.url} `);
                if (currentTab.id !== currentTabId || currentTab.windowId !== currentWindowId) {
                    console.consoleLogError(constants.NAV_CONTROL, `Error getting current tab - CurrentWindowId : ${currentWindowId}, CurrentTabid: ${currentTabId} - ReceivedWindowId : ${currentTab.windowId}, ReceivedTabid: ${currentTab.id}`);
                    callBack("");
                }
                else {
                    var key = functions.getBrowsingPositionKey(currentWindowId, currentTab.id);
                    let currentTabUrl = "";
                    if (tabURLDict[key] !== undefined) {
                        if (functions.isNullOrEmpty(tabURLDict[key].url)){
                            console.consoleLogError(constants.NAV_CONTROL, `Current tab info incorrect - CurrentWindowId : ${currentWindowId}, CurrentTabid: ${currentTabId} - ReceivedWindowId : ${currentTab.windowId}, ReceivedTabid: ${currentTab.id} - tab.url : ${tabURLDict[key].url} - tab.completed : ${tabURLDict[key].completed}`);
                            callBack("");
                        }
                        currentTabUrl = tabURLDict[key].url;
                        console.consoleLogForce(constants.NAV_CONTROL, `getCurrentTabURL : Current tab URL on the fly: ${currentTabUrl}`);

                    }
                    else {
                        console.consoleLogForce(constants.NAV_CONTROL, `getCurrentTabURL :  Tab ID: [${currentTab.id}] not found in tabURLDict for url:[${currentTab.url}] `);
                        tabURLDict[key] = functions.getTabItem(currentTab.url, "", false);
                        currentTabUrl = currentTab.url;

                    }
                    console.consoleLogForce(constants.NAV_CONTROL, `getCurrentTabURL returned : ${currentTabUrl}`);
                    callBack(currentTabUrl);
                }
            }
            else {
                console.consoleLogError(constants.NAV_CONTROL, `getCurrentTabURL : No active tab for the request windowId  [${currentWindowId}]`);
                callBack("");
            }
        }
        else
        {
            console.consoleLogError(constants.NAV_CONTROL, `getCurrentTabURL : No tabs for windowsId [${currentWindowId}]`);
        }
    });
}

///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
////////////////////// OVERRIDE BROWSER EVENTS METHODS ////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////

function onConnect(port) {
    port.onMessage.addListener(function (message) {

        if (message.from && message.from === 'popup' && message.start && message.start === 'Y') {
            // @ts-ignore
            let url = "chrome://extensions/?id=" + chrome.runtime.id;
            switch (constants.originName) {

                // @ts-ignore
                case "firefox":
                    // @ts-ignore
                    let userLang = navigator.language || navigator.userLanguage;
                    let lang = userLang.substring(0, 2).toLowerCase();
                    switch (lang) {
                        case "es":
                            url = "https://support.mozilla.org/es-ES/kb/extensions-private-browsing";
                            break;
                        case "pt":
                            url = "https://support.mozilla.org/pt-BR/kb/extensions-private-browsing";
                            break;
                        case "ca":
                            url = "https://support.mozilla.org/ca-CA/kb/extensions-private-browsing";
                            break;
                        case "en":
                        default:
                            url = "https://support.mozilla.org/en-US/kb/extensions-private-browsing";
                            break;
                    }

                    break;
                // @ts-ignore
                case "msedge":
                    // @ts-ignore
                    url = "edge://extensions/?id=" + chrome.runtime.id;
            }
            // @ts-ignore
            chrome.tabs.create({ url: url });
        }
    });
};

function onCompleted(details)  {
    if (details.frameType=="outermost_frame"){
        console.consoleLogForce(constants.NAV_CONTROL, `onCompleted : CurrentWindowId : ${currentWindowId} - CurrentTabid: ${currentTabId} - tabid: ${details.tabId} - URL : ${details.url}`);

        const url = details.url;
        const key = functions.getBrowsingPositionKey(currentWindowId, details.tabId);
        if (tabURLDict[key]?.url == url) {
            tabURLDict[key].completed = true;
            console.consoleLogForce(constants.NAV_CONTROL, `onCompleted : URL has been complited in tabURLDict: [${key}] : [${url}]`);
        }
    }
};

function onBeforeNavigate(details){
    if (details.frameType=="outermost_frame"){
        console.consoleLogForce(constants.NAV_CONTROL, `onBeforeNavigate : CurrentWindowId : ${currentWindowId} - CurrentTabid: ${currentTabId} - tabId: ${details.tabId}  - type: ${details.frameType}`);
        let t = details.tabId;
        let newKey = functions.getBrowsingPositionKey(currentWindowId, t);
        // @ts-ignore
        const url = details.url;

        tabURLDict[newKey] = functions.getTabItem(details.url,"", false);
        console.consoleLogForce(constants.NAV_CONTROL, "onBeforeNavigate : URL has been added to tabURLDict: "+  details.url);
    }
};

async function onWindowRemoved(windowId)
{
    let lastwindow = await isLastWindow();
    if (functions.isVersion1()) {
        Object.keys(tabURLDict).forEach(key => {
            if (key.startsWith(windowId + "-")) {
                delete tabURLDict[key];
            }
        });
    }
    // comprobar que no existen mas ventanas abiertas
    console.consoleLogForce(constants.NAV_CONTROL, "BROWSER: window removed");
    if (lastwindow && commChannel) {
        console.consoleLogForce(constants.NAV_CONTROL, "Comm is active. Gonna be finalize");
        suspended = true;
        let newMessage = { "messageType": "finalize"};
        postMessage(newMessage);
        // @ts-ignore
        commChannel.disconnect();
        commChannel = null;
    }

    console.consoleLogForce(constants.NAV_CONTROL, `Window removed: ${windowId}`);
}

async function onSuspend()
{
    console.consoleLogForce(constants.NAV_CONTROL, "BROWSER: Browser suspended");
    let lastwindow = isLastWindow();
    if (lastwindow && commChannel) {
        console.consoleLogForce(constants.NAV_CONTROL, "Comm is active. Gonna be finalize");
        suspended = true;
        let newMessage = { "messageType": "finalize"};
        postMessage(newMessage);
        // @ts-ignore
        commChannel.disconnect();
        commChannel = null;
    }
}

// This method set the window and tab id after activate a different window or tab
// for version1 it sends the registered url for the current window and tab
function onTabActivated(WindowAndTabInfo)
{
    let w = WindowAndTabInfo.windowId;
    let t = WindowAndTabInfo.tabId;
    let tabKey = functions.getBrowsingPositionKey(w, t);
    console.consoleLogForce(constants.NAV_CONTROL, `onTabActivated : CurrentWindowId : ${currentWindowId} - CurrentTabid: ${currentTabId} - Received windowId: ${w}, received tabId: ${t}`);
    if (currentTabId !== t || currentWindowId !== w) {
        if (tabKey in tabURLDict) {
            if (functions.isVersion1()) {
                postMessage(tabURLDict[tabKey].message);
                console.consoleLogForce(constants.NAV_CONTROL, "onTabActivated: Sent current URL " + tabURLDict[tabKey].message.url);
            }
        }
        if (!tabsMode[t]){
            handlinghosts.getUnknowTabIncognitoState();
        }
        currentTabId = t;
        currentWindowId = w
    }
}

function onTabCreated(tabInfo)
{
    let w = tabInfo.windowId;
    let t = tabInfo.id;
    console.consoleLogForce(constants.NAV_CONTROL, `onTabCreated : Received windowId: ${w}, received tabId: ${t}, mode incognit: ${tabInfo.incognito}`);
    tabsMode[tabInfo.id] = tabInfo.incognito;
    currentTabId = t;
    currentWindowId = w
}

function onTabRemoved(tabInfo, removeInfo)
{
    console.consoleLogForce(constants.NAV_CONTROL, `onTabRemoved : Received windowId: ${removeInfo.windowId}, received tabId: ${tabInfo}`);
    delete tabsMode[tabInfo]

}

function onWindowFocusChanged(windowId) {

    if (windowId === -1){
        return; //discard the popup: certificates, notifications, ...
    }
    console.consoleLogForce(constants.NAV_CONTROL, `onWindowFocusChanged :  Current windowId: ${currentWindowId}, current tabId: ${currentTabId}, received windowId: ${windowId}`);
    if (windowId !== currentWindowId) {
        currentWindowId = windowId;
        findCurrentTab();
        console.consoleLogForce(constants.NAV_CONTROL, `onWindowFocusChanged : Setted new currentWindowId : ${windowId}`);
    }

}

///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////      OVERRIDE BROWSER NAVIGATION EVENTS METHODS      //////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////


function beforeRedirect(info) {
    if (info.frameType=="outermost_frame"){
        let initiator = info.initiator;
        // @ts-ignore
        if (constants.originName === "firefox") {
            initiator = info.originUrl;
        }

        console.consoleLogForce(constants.NAV_CONTROL, `beforeRedirect initiator : ${initiator} - redirectUrl : ${info.redirectUrl} - url : ${info.url}`);
        if (!cancelCurrentNavigation &&
            info.type === 'main_frame' &&
            info.statusCode == '302') {
                if (!functions.isNullOrEmpty(handlinghosts.getContainerIdByUrl(info.redirectUrl))) {
                    let containerIdInitiator = handlinghosts.getContainerIdByUrl(initiator);
                    let containerIdURL = handlinghosts.getContainerIdByUrl(info.url);

                    if (!functions.isNullOrEmpty(containerIdInitiator) && containerIdInitiator == containerIdURL) {
                        console.consoleLogForce(constants.NAV_CONTROL, "beforeRedirect manage redirectUrl");
                        let host = (new URL(info.redirectUrl)).host;
                        let issuer = (new URL(initiator)).host;
                        //success with OPENID

                        var newelement = false;
                        if (handlinghosts.getContainerIdByHost(host) == "") {
                            newelement = true;
                            console.consoleLogForce(constants.OPENID, `register new openId origin host [${host}]`);
                            handlinghosts.addUpNewHandledHost(containerIdInitiator, host, issuer, constants.OPENID, constants.OPENID);
                        }

                        let resultPolicy = regex.checkAllowURL(policyDict[containerIdInitiator], info.redirectUrl);
                        if (resultPolicy.result) {

                            if (newelement){
                                notifyNewOrigin(info.redirectUrl, issuer, resultPolicy.policyId, resultPolicy.filterId, containerIdInitiator);
                            }
                            return true;
                        } else {
                            console.consoleLogForce(constants.OPENID, `Blocked by policy : host [${info.redirectUrl}], policyId [${resultPolicy.policyId}], filterId [${resultPolicy.filterId}], containerID [${containerIdInitiator}]`);
                            deniedURLDict[generateDictionaryKey(host)] = handlinghosts.createDeniedHostListElement(containerIdInitiator, constants.OPENID);
                            notifyBlockPage(info.redirectUrl, issuer, resultPolicy.policyId, resultPolicy.filterId, containerIdInitiator);
                            beforeRedirectBlocking = true;
                            return false;
                        }
                    }
                }
        }
    }
}

function beforeRequest(info) {
    try {
        /*let param = (new URLSearchParams(info.url)).get("fakeRTTestBlockPage");  // THIS CODE PUPOSSE IS TO ALLOW US CHECK THE REDIRECT PAGE AN ALL HIS POSSIBLITIES. iT COULD BE DELTED OR COMMENTED
        if (!functions.isNullOrEmpty(param))
        {
            console.consoleLogDebug(constants.NAV_REQUEST, "***********************************************");
            console.consoleLogForce(constants.NAV_REQUEST, "REDIRECT CHECK.");
            console.consoleLogForce(constants.NAV_REQUEST, `URL : {${info.url}}`);
            console.consoleLogDebug(constants.NAV_REQUEST, "***********************************************");
            return beforeRequestRedirect(info.tabId, param); //Redirect
        }*/

        if (tabsMode[info.tabId] == null && info.tabId >= 0)
            {
                getTabMode(info.tabId);
            }

        if (!info.hasOwnProperty('url')) {
            console.consoleLogDebug(constants.NAV_REQUEST, `BeforeRequest got an unhandled object type that doesn't define a url property [{${JSON.stringify(info, null, 2)}]`);
            return { cancel: false };
        }
        console.consoleLogDebug(constants.NAV_REQUEST, `BeforeRequest {${info.url}}`);
        cancelCurrentNavigation = false;
        if (!tabsMode[info.tabId]){
            handlinghosts.getUnknowTabIncognitoState();
        }
        if (blockByTamper) {
            console.consoleLogForce(constants.NAV_REQUEST, `POSSIBLE TAMPER. BLOCKING ALL NAVIGATION - URL : {${info.url}}`);
            return responseCancelNavigation(info.tabId); 
        }

        if (blockByWrongPoliciesProcessException) {
            console.consoleLogForce(constants.NAV_REQUEST, `WRONG POLICIES PROCESS. BLOCKING ALL NAVIGATION - URL : {${info.url}}`);
            return responseCancelNavigation(info.tabId); 
        }

        if (blockByWrongPoliciesProcessEmpty) {
            console.consoleLogForce(constants.NAV_REQUEST, `WRONG POLICIES PROCESS. BLOCKING ALL NAVIGATION - URL : {${info.url}}`);
            return responseCancelNavigation(info.tabId);
        }

        let urlcalled = (new URL(info.url));
        if (beforeRedirectBlocking) {
            beforeRedirectBlocking = false;
            console.consoleLogForce(constants.NAV_REQUEST, `FROM REDIRECT EVENT BLOCKING. WRONG OPENID PROCESS - URL : {${info.url}}`);
            return responseCancelNavigation(info.tabId); 
        }

        let result = openId.handleOpenId(urlcalled)
        // @ts-ignore
        if (!result.result) {
            // @ts-ignore
            if(result.policy){
                console.consoleLogForce(constants.NAV_REQUEST, `WRONG OPENID PROCESS - CANCEL`);
                return responseCancelNavigation(info.tabId); 
            } else {
                console.consoleLogForce(constants.NAV_REQUEST, `POSSIBLE TAMPER. WRONG OPENID PROCESS - TAMPER - URL : {${info.url}}`);
                return responseCancelNavigation(info.tabId); 
            }
        }

        if(handlinghosts.getIsPreviouslyDeniedUrl(urlcalled.host))
        {
            return responseCancelNavigation(info.tabId);
        }

        let currentUrl = "";
        if (!cancelCurrentNavigation && (info.type === 'main_frame')) {
            currentUrl = info.url;

            // set current page must be first step
            let postData = "";
            if (info.requestBody != null) {
                postData = btoa(JSON.stringify(info.requestBody.formData)); //encode to base64
            }

            sendCurrentURLToRTService(functions.getBrowsingPositionKey(currentWindowId, info.tabId), currentUrl, postData);
            if (info.method === "GET") 
            {     
                const requeststring =  urlcalled.searchParams.get("SAMLRequest");
                if (requeststring != null && requeststring != ""){
                    decodeSAMLRequest(requeststring).then(samlstring =>{
                        const samlRequest = {
                            GetCall: true,
                            SAMLRequest:  samlstring
                        };
                        saml.checkSAMLAssertion(info.url,
                        JSON.stringify(samlRequest),
                        info.initiator);
                    });
                    return { cancel: false };
                }
            }

            if (info.requestBody != null) {
                let samlResult = saml.checkSAMLAssertion(info.url,
                    JSON.stringify(info.requestBody.formData),
                    info.initiator);
                if (!samlResult.result)
                {
                    if(samlResult.policy){
                        console.consoleLogForce(constants.NAV_REQUEST, `WRONG SAMLRESPONSE PROCESS - CANCEL`);
                        return responseCancelNavigation(info.tabId); 
                    } else {
                        console.consoleLogForce(constants.NAV_REQUEST, `WRONG SAMLRESPONSE PROCESS - TAMPER - URL : {${info.url}}`);
                        console.consoleLogForce(constants.NAV_REQUEST, `URL : {${info.url}} should have been blocked; however, saml platform errors are being allowed temporarily`);
                      //  return responseCancelNavigation(info.tabId);
                      return { cancel: false };
                    }
                }
            }

            let containerId = handlinghosts.getContainerIdByUrl(currentUrl);
            if (!functions.isNullOrEmpty(containerId)) {
                try
                {
                    let element = handlinghosts.getHostElement((new URL(currentUrl)).host, true);
                    if (element.mappedSites.triggerEvent == true && element.mappedSites.eventCreated == false) {
                        notifyAllowed(currentUrl, info.url, element.mappedSites.policyId, element.mappedSites.appGroupId, containerId);
                        element.mappedSites.eventCreated = true;
                    }

                    let policyResult = regex.checkAllowURL(policyDict[containerId], currentUrl);
                    if (!policyResult.result) {
                        if (policyResult.policy){
                            console.consoleLogForce(constants.NAV_REQUEST, `NAVIGATION CANCELED BY POLICY - URL : {${info.url}} - Policy Id : {${policyResult.policyId}} - Filter Id : {${policyResult.filterId}} - ContainerId : {${containerId}} - Protocol : {${element.protocol}}`);
                            notifyBlockPage(currentUrl, element.protocol, policyResult.policyId, policyResult.filterId, containerId);
                            return responseCancelNavigation(info.tabId);
                        } else {
                            console.consoleLogForce(constants.NAV_REQUEST, `NAVIGATION CANCELED BY POLICY PROCESS WITH ERROR - URL : {${info.url}} - ContainerId : {${containerId}}`);
                            return responseCancelNavigation(info.tabId);
                        }
                    }
                }catch (error) {
                        console.consoleLogError(constants.NAV_REQUEST, "An exception thow in a beforeRequest event in a handled url", getErrorMessage(error));
                        return responseCancelNavigation(info.tabId);
                }
            }

        }
        if (cancelCurrentNavigation) {
            console.consoleLogForce(constants.NAV_REQUEST, `NAVIGATION CANCELED. Inherit from a different point - URL : {${info.url}}`);
            return responseCancelNavigation(info.tabId); 
        }
        return { cancel: false };
    }catch (error) {
        console.consoleLogError(constants.NAV_REQUEST, "An exception thow in a beforeRequest event", getErrorMessage(error));
        return { cancel: false };
    }finally {
        cancelCurrentNavigation = false;
    }
}

async function decodeSAMLRequest(text) {

  const binary = atob(text);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binary.charCodeAt(i);
  }

  const ds = new DecompressionStream('deflate-raw');
  const decompressedStream = new Blob([bytes]).stream().pipeThrough(ds);
  const xml = new Response(decompressedStream).text();

  return xml;
}

function responseCancelNavigation(tabId) {
    console.consoleLogDebug(constants.CANCELATION, "Starting responseCancelNavigation");
    if (certificateWasRequested)
    {        
        console.consoleLogDebug(constants.CANCELATION, "responseCancelNavigation canceled");
        return { cancel: true};
    }
    else
    {
        console.consoleLogError(constants.CANCELATION, "ResponseCancelNavigation cancelled. Certificate was not used");
    }
    return { cancel: false};
}

function sendCurrentURLToRTService(tabKey, currentUrl, postData) {
    //related to old system to get current url
    let message = { "messageType": "currentUrl", "url": currentUrl, "postData": postData };
    tabURLDict[tabKey] = functions.getTabItem(currentUrl, message, false);

    if (functions.isVersion1()) {
        postMessage(message); //Send message to host.
    }
}

///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
/////////////////////////     NOTIFICATION EVENTS   ///////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////

export function notifyBlockPage(currentUrl, urlOrigin, policyId, policeFilterId, containerID) {

    console.consoleLogForce(constants.NAV_REQUEST, `Notify: reportBLOCKING  - currentUrl : {${currentUrl}} - urlOrigin : {${urlOrigin}} - Policy Id : {${policyId}} - Filter Id : {${policeFilterId}} - ContainerId : {${containerID}}`);
    cancelCurrentNavigation = true;
    let message = { "messageType": "reportBlock", "process": constants.originName, "url": currentUrl, "urlOrigin": urlOrigin, "policyId": policyId, "policyFilterId": policeFilterId, "containerID": containerID }
    postMessage(message);
}

export function notifyNewOrigin(currentUrl, urlOrigin, policyId, policeFilterId, containerID) {
    console.consoleLogForce(constants.NAV_REQUEST, `Notify: report new origin - currentUrl : {${currentUrl}} - urlOrigin : {${urlOrigin}} - Policy Id : {${policyId}} - Filter Id : {${policeFilterId}} - ContainerId : {${containerID}}`);
    let message = { "messageType": "reportDelegate", "process": constants.originName, "url": currentUrl, "urlOrigin": urlOrigin, "policyId": policyId, "policyFilterId": policeFilterId, "containerID": containerID }
    postMessage(message);
}

export function notifyAllowed(currentUrl, urlOrigin, policyId, applicationGroupId, containerID) {
    console.consoleLogForce(constants.NAV_REQUEST, `Notify: report allowed - currentUrl : {${currentUrl}} - urlOrigin : {${urlOrigin}} - Policy Id : {${policyId}} - Application Group Id : {${applicationGroupId}} - ContainerId : {${containerID}}`);
    let message = { "messageType": "reportAllowed", "process": constants.originName, "url": currentUrl, "urlOrigin": urlOrigin, "policyId": policyId, "applicationGroupId": applicationGroupId, "containerID": containerID }
    postMessage(message);
}

///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
/////////////////////////        HANDLING POLICIES    /////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////

function processRawReceivedPolicies(message)
{
    let first = false;
    console.consoleLogForce(constants.POLICIES, `processRawReceivedPolicies start. containerId: [${message.containerID}]  url: [${message.url}]`)
    try {
        console.consoleLogDebug(constants.POLICIES, "Certificate using requested");
        certificateWasRequested = true // once we got p0licies from the agentservice a cetificate using was done, so we can handle the navigation, never before
        if (message.policies != null) {
            first = handlinghosts.getContainerIdByHost(message.url) == "";
            if (!functions.isVersion1()) {
                console.consoleLogForce(constants.POLICIES, `First step Received comprimed policies ${message.policies}`);
                message.policies = atob(message.policies);
            }

            console.consoleLogForce(constants.POLICIES, `Received policies  ${message.policies}`);
            policyDict[message.containerID] = JSON.parse(message.policies);
        }
        else
        {
            console.consoleLogError(constants.POLICIES, "Policies property is empty" );
            blockByWrongPoliciesProcessEmpty = true;
        }
    }
    catch (error) {
        blockByWrongPoliciesProcessException = true;
        console.consoleLogError(constants.POLICIES, "An error occurred processing raw policies", getErrorMessage(error));
    }
    return first;
}
function processAfterReceivedPolicies(first, message) {
    console.consoleLogForce(constants.POLICIES, "processAfterReceivedPolicies start")

    try{
        let protocol = "";
        let key = generateDictionaryKey(message.url);
        let authRequestSAMLItem = authRequestDict[key];
        let samlId = constants.PROTOCOL_NONE;
        if (authRequestSAMLItem == null && authRequestSAMLItem !== "undefined" ){ // look for the url inside the dictinary
            Object.entries(authRequestDict).forEach(([key, value]) => {
                if ( (new URL(value.url)).host == message.url && value.incognito == handlinghosts.isIncognito()){
                    authRequestSAMLItem = authRequestDict[key];
                    return;
                }
            });
        }
        let samlProtocol = (authRequestSAMLItem != null && authRequestSAMLItem != "undefined");
        let openIdProtocol = (first && message.url === constants.brasilOpenIDCertWeb);
        if(samlProtocol) {
            console.consoleLogForce(constants.POLICIES, `Got policies for a SAML authentication ${key}`);
            protocol = constants.SAML;
            samlId=samlProtocol.samlId;
        } else if(openIdProtocol) {
            console.consoleLogForce(constants.POLICIES, `Got policies for a OPENID authentication`);
            protocol = constants.PROTOCOL_OPENID;
        }

        handlinghosts.addUpNewHandledHost(message.containerID, message.url, message.url, protocol, samlId);

        if (protocol == constants.SAML){
            console.consoleLogForce(constants.POLICIES, `SAML add authRequestElement authentication. host: ${authRequestSAMLItem.host}`);
            // We are adding up the url that we've received from rtservice.
            // This url was directly allowed by the server using process so we don't check it
            handlinghosts.addUpNewHandledHost(message.containerID, authRequestSAMLItem.host, authRequestSAMLItem.host, protocol, samlId);

            // During the saml process the url that trigger the process is registered in the authRequestDict
            // Once the url that uses the certificate is allowed, we must check the previous url against our policies
            var resultPolicy = regex.checkAllowURL(policyDict[message.containerID], authRequestSAMLItem.urlHost);
            if (resultPolicy.result) {
                notifyNewOrigin(authRequestSAMLItem.urlHost, message.url, resultPolicy.policyId, resultPolicy.filterId, message.containerID);
            } else {
                console.consoleLogForce(constants.POLICIES, "SAML processAfterReceivedPolicies BLOCKEVERYTHING ON!!!");
                if (resultPolicy.policy) {
                    deniedURLDict[generateDictionaryKey(authRequestSAMLItem.urlHost)] = handlinghosts.createDeniedHostListElement(message.containerID, constants.SAML);
                    notifyBlockPage(authRequestSAMLItem.urlHost, message.url, resultPolicy.policyId, resultPolicy.filterId, message.containerID);
                }
                // When the storaged url is denied by policies the certificate using is already allowed
                // allowing users to nevigate freely
                // That leaves us just the option to block all the navigation in order to protect the system.
                blockByTamper = true;
            }
            console.consoleLogForce(constants.POLICIES, `SAML remove authRequestElement authentication ${key}`);
            delete authRequestDict[generateDictionaryKey(authRequestSAMLItem.host)]
        }

        if (first && message.url === constants.brasilOpenIDCertWeb) {
            console.consoleLogForce(constants.POLICIES, "OPENID: openIdRelatedDomains." + Object.keys(openIdRelatedDomains).length);
            if (Object.keys(openIdRelatedDomains).length != 0 &&
            // @ts-ignore
                !openId.AuthorizeOpenIdPath(message.containerID, message.url)) {
                // we got a certificate use with OPENID without a
                // correct previous process
                console.consoleLogForce(constants.POLICIES, "OPENID: we got a certificate using with OPENID without a correct previous process" );
                blockByTamper = true;
                console.consoleLogForce(constants.POLICIES, "BLOCKEVERYTHING ON!!!");
                return;
            }
        }
    }
    catch (error) {
        blockByWrongPoliciesProcessException = true;
        console.consoleLogError(constants.POLICIES, "An error occurred processing policies", getErrorMessage(error));
    }
}

///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
/////////////////////////            HELPERS        ///////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////

function getTabMode(tabId) {
    // @ts-ignore
    try {
    console.consoleLogDebug(constants.NAV_CONTROL, `getTabMode started  ${tabId}`);
    chrome.tabs.get(tabId,  function (tab) {

        if (chrome.runtime.lastError) {
            console.consoleLogError(constants.NAV_CONTROL, `Requested tab ${tabId} doesn't exists: ${getErrorMessage(chrome.runtime.lastError)}` );
        }

        tabsMode[tabId] = tab.incognito;

    });
    console.consoleLogDebug(constants.NAV_CONTROL, `getTabMode done  ${tabId}`);
    }catch (error) {
        console.consoleLogError(constants.NAV_REQUEST, "An error occurred getting Tab Mode", getErrorMessage(error));
    }
}

//related to old system to catch current url
//Configure events to control the current active tab
function findCurrentTab() {
    // @ts-ignore
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
        if (!tabs || tabs[0] == undefined)
        {
            return;
        }

        let activeTabId = tabs[0].id;
        if (tabs[0].windowId == currentWindowId)
        {
            if (currentTabId !== activeTabId) {
                var key = functions.getBrowsingPositionKey(currentWindowId, activeTabId);
                if (functions.isVersion1() && key in tabURLDict) {
                    postMessage(tabURLDict[key].message);
                }
                console.consoleLogDebug(constants.NAV_CONTROL, `findCurrentTab. Current currentTabId and the given activeTabId are different. CurrentTabId was changed to ${activeTabId}`);
                currentTabId = activeTabId;
            }
        }
        else
        {
            console.consoleLogError(constants.NAV_CONTROL, `findCurrentTab. Current windowId and the given windowid are different. CurrentTabId was changed to -1`);
            currentTabId = -1;
        }
    });

}

export function clearDictionarys(protocol){
    let isIncognito = handlinghosts.isIncognito();
    handledHostsList = handledHostsList.filter((d) => !(d.protocol == protocol && d.incognito == isIncognito));
    deniedURLDict = Object.fromEntries(Object.entries(deniedURLDict).filter(([k,d]) => !(d.protocol == protocol && d.incognito == isIncognito)));
    openIdRelatedDomains = Object.fromEntries(Object.entries(openIdRelatedDomains).filter(([k,d]) => !(d.protocol == protocol && d.incognito == isIncognito)));
    openIdAlreadyLogged = Object.fromEntries(Object.entries(openIdAlreadyLogged).filter(([k,d]) => !(d.protocol == protocol && d.incognito == isIncognito)));
    authRequestDict = Object.fromEntries(Object.entries(authRequestDict).filter(([k,d]) => !(d.protocol == protocol && d.incognito == isIncognito)));
}

export function generateDictionaryKey(value) {
    let incognito = handlinghosts.isIncognito();
    return `${value}_${incognito}`;
}

export function setTamper(){
    blockByTamper = true;
}

function getErrorMessage(error){
    if (error instanceof DOMException) {
        return error.message;
    }
    return error;
}

async function isLastWindow()
{
    try {
        const allWindows = await chrome.windows.getAll();
        if (allWindows.length === 0) {
          return true;
        }
    } catch  {

    }
    return false;
}

///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
/////////////////////////          On Load calls    ///////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////


/////////////////////////         OVERRIDE EVENTS   ///////////////////////////////

// @ts-ignore
chrome.webRequest.onBeforeRequest.addListener(beforeRequest, { urls: ["http://*/*", "https://*/*"] }, ["requestBody", "blocking"]);
// @ts-ignore
chrome.webRequest.onBeforeRedirect.addListener(beforeRedirect, { urls: ["http://*/*", "https://*/*"] }, ["responseHeaders"]);

// @ts-ignore
chrome.windows.onRemoved.addListener(onWindowRemoved);
// @ts-ignore
chrome.windows.onFocusChanged.addListener(onWindowFocusChanged);

// @ts-ignore
chrome.tabs.onCreated.addListener(onTabCreated);
// @ts-ignore
chrome.tabs.onActivated.addListener(onTabActivated);
// @ts-ignore
chrome.tabs.onRemoved.addListener(onTabRemoved);

// @ts-ignore
chrome.webNavigation.onBeforeNavigate.addListener(onBeforeNavigate);
// @ts-ignore
chrome.webNavigation.onCompleted.addListener(onCompleted);

// @ts-ignore
chrome.runtime.onConnect.addListener(onConnect);
// @ts-ignore
chrome.runtime.onSuspend.addListener(onSuspend);

/////////////////////////         Start!   ///////////////////////////////

initialize();
