import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { Wallet } from "ethers";
import { createAccount, createClient, parseStakingAmount } from "genlayer-js";
import * as chains from "genlayer-js/chains";


const [operation, txId, bond = ""] = process.argv.slice(2);
if (!operation || !/^0x[0-9a-fA-F]{64}$/.test(txId || "")) {
  throw new Error("Usage: genlayer_protocol.mjs <appeal|finalize> <tx-hash> [bond]");
}

const home = os.homedir();
const configPath = process.env.GENLAYER_CONFIG_PATH || path.join(home, ".genlayer", "genlayer-config.json");
const config = JSON.parse(await fs.readFile(configPath, "utf8"));
const networkName = process.env.GENLAYER_NETWORK || config.network || "studionet";
const chain = chains[networkName];
if (!chain) throw new Error(`Unsupported GenLayer network: ${networkName}`);

let privateKey = process.env.GENLAYER_PRIVATE_KEY || "";
if (!privateKey) {
  const accountName = process.env.GENLAYER_ACCOUNT_NAME || config.activeAccount;
  const keystorePath = process.env.GENLAYER_KEYSTORE_PATH
    || path.join(home, ".genlayer", "keystores", `${accountName}.json`);
  const password = process.env.GENLAYER_ACCOUNT_PASSWORD || "";
  if (!password) throw new Error("GENLAYER_ACCOUNT_PASSWORD is required to decrypt the GenLayer keystore");
  const wallet = await Wallet.fromEncryptedJson(await fs.readFile(keystorePath, "utf8"), password);
  privateKey = wallet.privateKey;
}

const account = createAccount(privateKey);
const client = createClient({ chain, account });
let hash;
if (operation === "appeal") {
  const args = { txId };
  if (bond) args.value = parseStakingAmount(bond);
  hash = await client.appealTransaction(args);
} else if (operation === "finalize") {
  hash = await client.finalizeTransaction({ txId });
} else {
  throw new Error(`Unsupported protocol operation: ${operation}`);
}

console.log(JSON.stringify({ operation, transaction_hash: hash, protocol_transaction_hash: txId }));
