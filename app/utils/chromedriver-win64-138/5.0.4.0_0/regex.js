import * as constants from './constants.js';

import {
    consoleLogDebug,
    consoleLogForce,
    consoleLogError,
} from './console.js'; //Required to UnitTesting

function RemoveUriProtocol(url) {
    try
    {
        consoleLogDebug(constants.REGEX, `Remove protocol : URL : ${url}`);
        let start = new URL(url).protocol.length + 2;
        let result = url.substring(start);
        consoleLogForce(constants.REGEX, `Remove protocol result : URL : ${result}`);
        return result;
    }catch (error){
        consoleLogError(constants.REGEX, 'RemoveUriProtocol throws a exception : ',error);        
    } 
    return url;
}

export function AddExpressionBeginAndEnd(expression) {
    consoleLogDebug(constants.REGEX, `Change expresion : Original : ${expression}`);
    let result ="";
    
    if (!String(expression).startsWith("^")) {
        result = "^" + expression;
    }
    else{
        result = expression;
    }

    if (!String(expression).endsWith("$")) {
        result += "$";
    }
    
    consoleLogForce(constants.REGEX, `Change expresion : Result : ${result}`);
    return result;
}


export function CheckRegexMatch(regex, textToCheck) {
    let result;
    try{   
        consoleLogDebug(constants.REGEX, `CheckRegexMatch. comparing [${textToCheck}] with [${regex}]`);
        let regexresult = new RegExp(regex, "i"); // "i" is case insensitive
        result = textToCheck.match(regexresult);
        consoleLogForce(constants.REGEX, `CheckRegexMatch. result [${result}]`);
        
    }catch (error){
        consoleLogError(constants.REGEX, 'CheckRegexMatch Error : ', error);        
    } 
    return result;
   
}

export function prepareURLtoTestRTRegExp(uri, expression) {

    var urlToReturn = ""
    try{
        consoleLogForce(constants.REGEX, `prepareURLtoTestRTRegExp. URL [${uri}] expression [${expression}]`);
        var url = new URL(uri);
        var start = url.protocol.length + 2;
        var uriWithoutProtocol = uri.slice(start);
        let substringValue = 0;

        if(CheckRegexMatch(expression, url.host)){
            consoleLogForce(constants.REGEX, `prepareURLtoTestRTRegExp. Expression is equal to domain`);
            return url.host;
        }
        
        consoleLogForce(constants.REGEX, `prepareURLtoTestRTRegExp. Removing protocol`);
    
        if(!uriWithoutProtocol.includes("/") && !uriWithoutProtocol.includes("?")){
            consoleLogForce(constants.REGEX, `Result : ${uri.slice(start)}`);
            return uri.slice(start);
        }

        if(uri.slice(-1)=="/" || url.pathname.length > 1 || url.hash != ""){
            if(url.hash != ""){
                consoleLogForce(constants.REGEX, `prepareURLtoTestRTRegExp. URL has hash`);
                substringValue = uri.length - url.hash.length - url.pathname.length - url.search.length;
            }else{
                consoleLogForce(constants.REGEX, `prepareURLtoTestRTRegExp. URL ended with SLASH`);
                substringValue = uri.length - url.pathname.length - url.search.length;
            }  
        }else if((uriWithoutProtocol.split("/").length - 1) == 1 && url.search.length>0){
            substringValue = uri.length - url.pathname.length - url.search.length;
        }
        else{
            substringValue = uri.length - url.search.length;
        }
    
        urlToReturn = uri.substring(start,substringValue); //GET HOST WITH OR WITHOUT PORT
        consoleLogForce(constants.REGEX, `prepareURLtoTestRTRegExp. Removing protocol. [${urlToReturn}]`);
        if(expression.includes("\\?")){
            if(uriWithoutProtocol.includes("/")){
                consoleLogForce(constants.REGEX, `prepareURLtoTestRTRegExp. URL includes PATH and QUERY`);
                urlToReturn = urlToReturn + url.pathname + url.search;
            }else{
                consoleLogForce(constants.REGEX, `prepareURLtoTestRTRegExp. URL includes QUERY`);
                urlToReturn = urlToReturn +  url.search;
            }
                
        }
        else if(expression.includes("/")){
            if(uriWithoutProtocol.includes("/")){
                consoleLogForce(constants.REGEX, `prepareURLtoTestRTRegExp. URL includes PATH`);
                urlToReturn = urlToReturn + url.pathname;
            }
        }
        else
        {
            consoleLogForce(constants.REGEX, `prepareURLtoTestRTRegExp. URL isolated [${urlToReturn}]`);
        }
    }catch (error){
        consoleLogError(constants.REGEX, `prepareURLtoTestRTRegExp Error while trying to prepare URL to Test RT Regluar Expressions, returning original URL: [${uri}] `, error);
        urlToReturn = uri;
    } 
    consoleLogForce(constants.REGEX, `Finally returning [${urlToReturn}]`);
    return urlToReturn;
}

function checkPolicyGroup(textExp, group) {  
    var result = false;
    try{
        consoleLogForce(constants.REGEX, `CheckPolicyGroup. [${group.value}]`);  
        if (group.whereExpType == constants.whereExpTypeSites || group.whereExpType == constants.whereExpTypeSitesValue) {
            consoleLogDebug(constants.REGEX, `Evaluate policy as SITE. whereExpType: ${group.whereExpType}`);
            result= CheckSiteExprMatch(group.value, textExp);
        }
        else {
            consoleLogDebug(constants.REGEX, `Evaluate policy as REGEX. whereExpType: ${group.whereExpType}`);
            result= CheckRegExprMatch(group.value, textExp);
        }
    }catch (error){
        consoleLogError(constants.REGEX, `CheckPolicyGroup Error while trying to check policy group`, error);
    }
    return result;
}

export function CheckSiteExprMatch(regex,textToCheck){
    try{
        consoleLogForce(constants.REGEX, `CheckSiteExprMatch. checking RT Sites type`);    
        regex = AddExpressionBeginAndEnd(regex) //Duplicated between the two check for unitTesting
        textToCheck = prepareURLtoTestRTRegExp(textToCheck, regex)

        if (CheckRegexMatch(regex, textToCheck))
        {
            consoleLogForce(constants.REGEX, `CheckSiteExprMatch. result ok`);
            return true;
        } 
        consoleLogForce(constants.REGEX, `CheckSiteExprMatch. result ko`);
    }catch (error){
        consoleLogError(constants.REGEX, `CheckSiteExprMatch Error while trying to check site expression match`, error);
    }
    return false;       
}

export function CheckRegExprMatch(regex,textToCheck){
    try{
        consoleLogForce(constants.REGEX, `CheckRegExprMatch. checking REGEX type`);
        regex = AddExpressionBeginAndEnd(regex) //Duplicated between the two check for unitTesting
        textToCheck = RemoveUriProtocol(textToCheck);
        if (CheckRegexMatch(regex, textToCheck))
        {
            consoleLogForce(constants.REGEX, `CheckRegExprMatch. result ok`);
            return true;
        }
        consoleLogForce(constants.REGEX, `CheckRegExprMatch. result ko`);
    }catch (error){
        consoleLogError(constants.REGEX, `CheckRegExprMatch Error while trying to check regex expression match`, error);
    }
    return false;        
}

function CheckPolicy(textExp, policy, policyForDisallow) {
    let idAppFilter = 0;
    let result = false
    var groupValue = '';
    try {
        consoleLogForce(constants.REGEX, `CheckPolicy starts. text [${textExp}]  policyfordisallow [${policyForDisallow}]`);
        policy.Groups.some(group => {
            groupValue = group.value;
            consoleLogForce(constants.REGEX, `CheckPolicy group. [${group.idAppFilter}]`);
            result = checkPolicyGroup(textExp, group);
            if (result) {
                consoleLogForce(constants.REGEX, `CheckPolicy group. [${group.idAppFilter}] result :  [${result}] `);
                idAppFilter = group.idAppFilter;
                consoleLogForce(constants.REGEX, `CheckPolicy done `);
                return result; //required for ".some" function
            }
            consoleLogForce(constants.REGEX, `CheckPolicy group. [${group.idAppFilter}] result :  [${result}] `);
        });
    }
    catch (error) {
        consoleLogError(constants.REGEX, "testRTExp. ERROR comparing [" + textExp + "] with [" + groupValue + "]\n" , error);
        result = policyForDisallow;
    }
    return { result: result, filterId : idAppFilter };
}



function checkAllowURLREGEXP(policy, urlToCheck, whereList, policyForDisallow) {
    let result = false;
    let navigationResult = constants.PolicyActionEnum_DISALLOW;
    let idAppFilter = 0;
    consoleLogForce(constants.REGEX, `checkAllowURLREGEXP starts `);
    whereList.forEach(where => {
        try {
            let testRTExpResult = CheckPolicy(urlToCheck, where, policyForDisallow);

            consoleLogForce(constants.REGEX, `checkAllowURLREGEXP. where : ${where.groupName} `);
            if (testRTExpResult.result) { //result of CheckPolicy

                result = true;
                idAppFilter = testRTExpResult.filterId; // filter applied ID
                policy.action.forEach(action => {
                    action.contextName = where.groupName;
                    navigationResult = constants.PolicyActionEnum_ALLOW;
                    if (action.type == constants.PolicyActionEnum_DISALLOW || action.type == constants.PolicyActionEnum_DISALLOW_value) {
                        navigationResult = constants.PolicyActionEnum_DISALLOW;
                        return;
                    }
                });
            }
        }
        catch (error) {
            consoleLogError(constants.REGEX, `checkAllowURLREGEXP exception.`, error);            
            navigationResult = constants.PolicyActionEnum_DISALLOW; 
            if (policyForDisallow) {
                navigationResult = constants.PolicyActionEnum_ALLOW;
            }
            result = false;            
        }
    });
    consoleLogForce(constants.REGEX, `checkAllowURLREGEXP ends : result : ${result}, navigationResult : ${navigationResult} idAppFilter : ${idAppFilter} `);
    return { result: result, navigationResult :  navigationResult, filterId: idAppFilter };
}


function CheckPolicyIsForDisallow(policy) {
    let result = false;
    try {
        consoleLogForce(constants.REGEX, `CheckPolicyIsForDisallow starts`);
        result = (policy.action[0].type == constants.PolicyActionEnum_DISALLOW || policy.action[0].type == constants.PolicyActionEnum_DISALLOW_value);
        consoleLogForce(constants.REGEX, `CheckPolicyIsForDisallow. result :  ${result}`);    
    }catch (error){
        consoleLogError(constants.REGEX, `CheckRegExprMatch Error while trying to check regex expression match`, error);
    }
    return result;
}


export function checkAllowURL(policies, currenturl) {
    try
    {
        if (policies != null) {
            consoleLogForce(constants.REGEX, `checkAllowURL starts. Policies:  ${policies.length}`);
        }
        else
        {
            consoleLogForce(constants.REGEX, `checkAllowURL starts. Policies:  nil`);
        }
        
        let appliedPolicy = 0;
        let idAppFilter = 0;
        let result = false;
        if (policies != null) {
            policies.forEach(policy => {            
                if (appliedPolicy == 0) {
                    consoleLogForce(constants.REGEX, `checkAllowURL. Policy:  ${policy.idPolicy}`);
                    let checkAllowURLREGEXPResult = checkAllowURLREGEXP(policy, currenturl, policy.where, CheckPolicyIsForDisallow(policy));

                    if (checkAllowURLREGEXPResult.result) // checkAllowURLREGEXP result
                    {
                        consoleLogForce(constants.REGEX, `checkAllowURL. Policy ${policy.idPolicy} has matched`);
                        appliedPolicy = policy.idPolicy;
                        idAppFilter = checkAllowURLREGEXPResult.filterId; // filter applied ID
                        result = !(checkAllowURLREGEXPResult.navigationResult == constants.PolicyActionEnum_DISALLOW); //navigationResult
                        consoleLogForce(constants.REGEX, `checkAllowURL. Policy ${policy.idPolicy} result ${result}`);
                        return;
                    }
                }
            });
        }
        consoleLogForce(constants.REGEX, `checkAllowURL. Method returns. result :${result} appliedPolicy : ${appliedPolicy}  idAppFilter :${idAppFilter}`);
        return checkAllowURLResult(result, appliedPolicy, idAppFilter, true); // pending for send events PR
    }catch (error) {
        consoleLogError(constants.NAV_REQUEST, "An exception thow processing checkAllowURL", error);
        return checkAllowURLResult(false,  0,  0, false); // pending for send events PR
    }

    function checkAllowURLResult(result, policyId, filterId, policy)
    {
        return { result: result, policyId: policyId, filterId: filterId, policy: policy };
    }
}
