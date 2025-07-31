/**
 * Discord Webhook Handler for Cloudflare Workers (TypeScript)
 * Verifies Ed25519 signature and forwards to AWS SQS
 */

interface Env {
  DISCORD_PUBLIC_KEY: string;
  AWS_REGION: string;
  AWS_ACCESS_KEY_ID: string;
  AWS_SECRET_ACCESS_KEY: string;
  SQS_QUEUE_URL: string;
}

interface DiscordInteraction {
  id?: string;
  type: number;
  user?: {
    id: string;
  };
  member?: {
    user: {
      id: string;
    };
  };
}

// Convert hex string to Uint8Array
function hexToUint8Array(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substr(i, 2), 16);
  }
  return bytes;
}

// Ed25519 signature verification using Web Crypto API
async function verifyDiscordSignature(request: Request, body: string, publicKey: string): Promise<boolean> {
  const signature = request.headers.get('X-Signature-Ed25519');
  const timestamp = request.headers.get('X-Signature-Timestamp');

  if (!signature || !timestamp) {
    console.log('Missing signature or timestamp headers');
    return false;
  }

  try {
    const enc = new TextEncoder();
    const message = enc.encode(timestamp + body);
    const sig = hexToUint8Array(signature);

    // Import the public key for Ed25519
    const key = await crypto.subtle.importKey(
      'raw',
      hexToUint8Array(publicKey),
      {
        name: 'Ed25519',
      },
      false,
      ['verify']
    );

    // Verify the signature
    const verified = await crypto.subtle.verify(
      'Ed25519',
      key,
      sig,
      message
    );

    console.log(`Signature verification result: ${verified}`);
    return verified;
  } catch (error) {
    console.error('Signature verification error:', error);
    return false;
  }
}

// Generate message group ID for FIFO queue deduplication
function generateMessageGroupId(body: string): string {
  try {
    const data: DiscordInteraction = JSON.parse(body);
    // Use interaction ID if available, otherwise use user ID + timestamp
    if (data.id) {
      return `interaction-${data.id}`;
    }
    const userId = data.user?.id || data.member?.user?.id;
    if (userId) {
      return `user-${userId}-${Date.now()}`;
    }
    return `default-${Date.now()}`;
  } catch (error) {
    console.error('Error parsing body for message group ID:', error);
    return `fallback-${Date.now()}`;
  }
}

// AWS SQS API signature helper
async function signAWSRequest(
  method: string,
  url: string,
  headers: Record<string, string>,
  body: string,
  accessKeyId: string,
  secretAccessKey: string,
  region: string
): Promise<Record<string, string>> {
  const encoder = new TextEncoder();

  // Create canonical request
  const canonicalHeaders = Object.keys(headers)
    .sort()
    .map(key => `${key.toLowerCase()}:${headers[key]}`)
    .join('\n');

  const signedHeaders = Object.keys(headers)
    .sort()
    .map(key => key.toLowerCase())
    .join(';');

  const payloadHash = Array.from(
    new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(body)))
  ).map(b => b.toString(16).padStart(2, '0')).join('');

  // Parse URL to get the correct path
  const urlObj = new URL(url);
  const canonicalUri = urlObj.pathname;
  const canonicalQueryString = urlObj.search.substring(1); // Remove leading '?'
  
  const canonicalRequest = [
    method,
    canonicalUri,
    canonicalQueryString,
    canonicalHeaders,
    '',
    signedHeaders,
    payloadHash
  ].join('\n');

  // Create string to sign
  const algorithm = 'AWS4-HMAC-SHA256';
  const timestamp = new Date().toISOString().replace(/[:\-]|\.\d{3}/g, '');
  const date = timestamp.substring(0, 8);
  const credentialScope = `${date}/${region}/sqs/aws4_request`;

  const canonicalRequestHash = Array.from(
    new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(canonicalRequest)))
  ).map(b => b.toString(16).padStart(2, '0')).join('');

  const stringToSign = [
    algorithm,
    timestamp,
    credentialScope,
    canonicalRequestHash
  ].join('\n');

  // Calculate signature step by step
  const kSecret = encoder.encode(`AWS4${secretAccessKey}`);
  
  const kDate = await crypto.subtle.importKey(
    'raw',
    kSecret,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const dateKey = new Uint8Array(await crypto.subtle.sign('HMAC', kDate, encoder.encode(date)));

  const kRegion = await crypto.subtle.importKey(
    'raw',
    dateKey,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const regionKey = new Uint8Array(await crypto.subtle.sign('HMAC', kRegion, encoder.encode(region)));

  const kService = await crypto.subtle.importKey(
    'raw',
    regionKey,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const serviceKey = new Uint8Array(await crypto.subtle.sign('HMAC', kService, encoder.encode('sqs')));

  const kSigning = await crypto.subtle.importKey(
    'raw',
    serviceKey,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const signingKey = new Uint8Array(await crypto.subtle.sign('HMAC', kSigning, encoder.encode('aws4_request')));

  const kFinal = await crypto.subtle.importKey(
    'raw',
    signingKey,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  const signature = Array.from(
    new Uint8Array(await crypto.subtle.sign('HMAC', kFinal, encoder.encode(stringToSign)))
  ).map(b => b.toString(16).padStart(2, '0')).join('');

  return {
    ...headers,
    'Authorization': `${algorithm} Credential=${accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`,
    'X-Amz-Date': timestamp
  };
}

// Send message to AWS SQS using fetch API
async function sendToSQS(body: string, env: Env): Promise<void> {
  const messageGroupId = generateMessageGroupId(body);
  const deduplicationId = `${messageGroupId}-${Date.now()}`;

  // Parse SQS URL to get region and queue name
  const url = new URL(env.SQS_QUEUE_URL);
  const region = env.AWS_REGION;

  // SQS API parameters
  const params = new URLSearchParams({
    'Action': 'SendMessage',
    'Version': '2012-11-05',
    'MessageBody': body,
    'MessageGroupId': messageGroupId,
    'MessageDeduplicationId': deduplicationId,
    'MessageAttribute.1.Name': 'source',
    'MessageAttribute.1.Value.DataType': 'String',
    'MessageAttribute.1.Value.StringValue': 'discord-webhook',
    'MessageAttribute.2.Name': 'timestamp',
    'MessageAttribute.2.Value.DataType': 'String',
    'MessageAttribute.2.Value.StringValue': new Date().toISOString()
  });

  const requestBody = params.toString();

  const headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Host': url.host
  };

  // Sign the request
  const signedHeaders = await signAWSRequest(
    'POST',
    env.SQS_QUEUE_URL,
    headers,
    requestBody,
    env.AWS_ACCESS_KEY_ID,
    env.AWS_SECRET_ACCESS_KEY,
    region
  );

  try {
    const response = await fetch(env.SQS_QUEUE_URL, {
      method: 'POST',
      headers: signedHeaders,
      body: requestBody
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`SQS API error: ${response.status} - ${errorText}`);
    }

    console.log('Message sent to SQS successfully');
  } catch (error) {
    console.error('Failed to send message to SQS:', error);
    throw error;
  }
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    // Only handle POST requests to /interactions path
    const url = new URL(request.url);
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }
    
    if (url.pathname !== '/interactions') {
      return new Response('Not found', { status: 404 });
    }

    try {
      // Read the request body
      const body = await request.text();

      // Verify Discord signature
      const isValidSignature = await verifyDiscordSignature(
        request,
        body,
        env.DISCORD_PUBLIC_KEY
      );

      if (!isValidSignature) {
        console.log('Invalid signature, rejecting request');
        return new Response('Unauthorized', { status: 401 });
      }

      console.log('Signature verified, processing webhook');

      // Parse the body to check for PING
      let webhookData: DiscordInteraction;
      try {
        webhookData = JSON.parse(body);
      } catch (error) {
        console.error('Failed to parse webhook body:', error);
        return new Response('Bad Request', { status: 400 });
      }

      // Handle Discord PING (type 1)
      if (webhookData.type === 1) {
        console.log('Received Discord PING, responding with PONG');
        return new Response(JSON.stringify({ type: 1 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
      }

      // Send to SQS asynchronously (don't wait for completion)
      ctx.waitUntil(
        sendToSQS(body, env).catch(error => {
          console.error('SQS send failed, but still returning 204 to Discord:', error);
        })
      );

      // Return immediate ACK response to Discord
      console.log('Webhook forwarded to SQS, returning ACK');
      return new Response(JSON.stringify({ type: 5 }), { 
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });

    } catch (error) {
      console.error('Error processing webhook:', error);
      return new Response('Internal Server Error', { status: 500 });
    }
  },
} satisfies ExportedHandler<Env>;