const moment = require('moment');

class TimeHelper {
    constructor() {
        this.name = 'time_helper';
        this.role = 'time assistant';
        this.team = 'default';
    }

    getCurrentTime() {
        return moment().format('HH:mm:ss');
    }

    getCurrentDate() {
        return moment().format('YYYY-MM-DD');
    }

    getCurrentDateTime() {
        return moment().format('YYYY-MM-DD HH:mm:ss');
    }

    assistWithTimeQuery() {
        const currentTime = this.getCurrentTime();
        console.log(`现在是${currentTime}`);
        return currentTime;
    }
}

module.exports = TimeHelper;