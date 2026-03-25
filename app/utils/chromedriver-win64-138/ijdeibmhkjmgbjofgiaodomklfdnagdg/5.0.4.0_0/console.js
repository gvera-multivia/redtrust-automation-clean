import * as constants from './constants.js';

//********************************************************/
//VARIABLES
//********************************************************/
let logLevel = constants.LOGLEVEL_LOW; //Define logLevel setted in Windows Registry



//********************************************************/
//FUNCTIONS
//********************************************************/
export function SetLogLevel(message) {
    if(message && "logLevel" in message) {
        logLevel = message.logLevel;
        consoleLogForce(constants.INITIALIZING, `Setted logLevel: ${logLevel}`);
    }
    consoleLogDebug(constants.INITIALIZING, "SetLogLevel done");
}

export function consoleLogDebug(origin, text) {
    if(logLevel >= constants.LOGLEVEL_HIGH) {
        consoleLog(origin, text);
    }
}

export function consoleLogInfo(origin, text) {
    if(logLevel >= constants.LOGLEVEL_MEDIUM) {
        consoleLog(origin, text);
    }
}

export function consoleLogForce(origin, text) {
    consoleLog(origin, text);
}

export function consoleLogError(origin, text, error) {
    consoleError(origin, text, JSON.stringify(error));
}

function consoleLog(origin, text) {
        console.log(`${origin} : ${text}`)
}

function consoleError(origin, text, error) {
    if (!error) {
        console.error(`${origin} : ${text}`);
    }
    else {
        console.error(`${origin} : ${text} ->`, error)
    }
}
