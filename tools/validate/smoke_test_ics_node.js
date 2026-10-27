#!/usr/bin/env node
"use strict";

const net = require("net");
const http = require("http");

const plcs = [
  ["Raw Materials", "10.0.50.101", [[0, 9]], 12],
  ["Brewhouse", "10.0.50.102", [[0, 10]], 16],
  ["Fermentation", "10.0.50.103", [[0, 10]], 64],
  ["Conditioning", "10.0.50.104", [[0, 14]], 32],
  ["Packaging", "10.0.50.105", [[0, 6]], 16],
  ["Utilities", "10.0.50.106", [[0, 6], [700, 5]], 16],
];

let transaction = 100;

function modbus(host, functionCode, start, count) {
  return new Promise((resolve, reject) => {
    const txid = ++transaction;
    const request = Buffer.alloc(12);
    request.writeUInt16BE(txid, 0);
    request.writeUInt16BE(0, 2);
    request.writeUInt16BE(6, 4);
    request.writeUInt8(1, 6);
    request.writeUInt8(functionCode, 7);
    request.writeUInt16BE(start, 8);
    request.writeUInt16BE(count, 10);

    const chunks = [];
    let expected = null;
    const socket = net.createConnection({host, port: 502});
    socket.setTimeout(3000);
    socket.on("connect", () => socket.write(request));
    socket.on("data", chunk => {
      chunks.push(chunk);
      const data = Buffer.concat(chunks);
      if (data.length >= 7 && expected === null) expected = 6 + data.readUInt16BE(4);
      if (expected !== null && data.length >= expected) {
        socket.end();
        if (data.readUInt16BE(0) !== txid || data.readUInt16BE(2) !== 0) return reject(new Error("invalid MBAP response"));
        const fn = data.readUInt8(7);
        if ((fn & 0x80) || fn !== functionCode) return reject(new Error(`Modbus exception ${data.subarray(7).toString("hex")}`));
        resolve(data.subarray(7, expected));
      }
    });
    socket.on("timeout", () => socket.destroy(new Error("timeout")));
    socket.on("error", reject);
  });
}

async function readRegisters(host, start, count) {
  const payload = await modbus(host, 3, start, count);
  if (payload.readUInt8(1) !== count * 2) throw new Error("unexpected register byte count");
  return Array.from({length: count}, (_, i) => payload.readUInt16BE(2 + i * 2));
}

async function readCoils(host, count) {
  const payload = await modbus(host, 1, 0, count);
  const values = [];
  for (let i = 0; i < count; i++) values.push(Boolean(payload.readUInt8(2 + Math.floor(i / 8)) & (1 << (i % 8))));
  return values;
}

function webCheck(name, url) {
  return new Promise(resolve => {
    const req = http.get(url, {timeout: 5000}, response => {
      response.resume();
      resolve({name, url, ok: response.statusCode >= 200 && response.statusCode < 400, status: response.statusCode});
    });
    req.on("timeout", () => req.destroy(new Error("timeout")));
    req.on("error", error => resolve({name, url, ok: false, error: error.message}));
  });
}

async function retry(operation, attempts = 3) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      await new Promise(resolve => setTimeout(resolve, 200));
    }
  }
  throw lastError;
}

async function main() {
  const result = {timestamp: new Date().toISOString(), vantage: "ics-fuxa-hmi container", plcs: [], web: []};
  for (const [name, host, ranges, coilCount] of plcs) {
    const item = {name, host, ok: false};
    try {
      item.registers = {};
      for (const [start, count] of ranges) item.registers[String(start)] = await retry(() => readRegisters(host, start, count));
      const coils = await retry(() => readCoils(host, coilCount));
      item.nonzero_registers = Object.values(item.registers).flat().filter(value => value !== 0).length;
      item.active_coils = coils.map((value, index) => value ? index : null).filter(value => value !== null);
      item.ok = item.nonzero_registers > 0;
      if (!item.ok) item.error = "all sampled holding registers are zero";
    } catch (error) {
      item.error = error.message;
    }
    result.plcs.push(item);
  }
  result.web.push(await webCheck("FUXA", "http://127.0.0.1:1881/home"));
  result.web.push(await webCheck("Scada-LTS", "http://10.0.40.20:8080/Scada-LTS/"));
  result.ok = [...result.plcs, ...result.web].every(item => item.ok);
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = result.ok ? 0 : 1;
}

main().catch(error => { console.error(error); process.exit(1); });
