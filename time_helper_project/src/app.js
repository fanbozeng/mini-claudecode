const TimeHelper = require('./index.js');

// Example usage
const timeHelper = new TimeHelper();

console.log('时间助手已启动！');
console.log(`当前日期: ${timeHelper.getCurrentDate()}`);
console.log(`当前时间: ${timeHelper.getCurrentTime()}`);
console.log(`完整日期时间: ${timeHelper.getCurrentDateTime()}`);

module.exports = timeHelper;