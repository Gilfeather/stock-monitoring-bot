use anyhow::{Result, anyhow};
use ed25519_dalek::{Verifier, VerifyingKey, Signature};

pub fn verify_signature(
    signature_hex: &str,
    timestamp: &str,
    body: &str,
    public_key_hex: &str,
) -> Result<bool> {
    // 署名長チェック
    if signature_hex.len() != 128 {
        return Ok(false);
    }

    // 公開鍵長チェック
    if public_key_hex.len() != 64 {
        return Ok(false);
    }

    // Hex文字列をバイトに変換
    let signature_bytes = hex::decode(signature_hex)
        .map_err(|_| anyhow!("Invalid signature hex"))?;
    let public_key_bytes = hex::decode(public_key_hex)
        .map_err(|_| anyhow!("Invalid public key hex"))?;

    // Ed25519キーと署名を作成
    let verifying_key = VerifyingKey::from_bytes(
        &public_key_bytes.try_into()
            .map_err(|_| anyhow!("Invalid public key length"))?
    ).map_err(|_| anyhow!("Invalid public key"))?;

    let signature = Signature::from_bytes(
        &signature_bytes.try_into()
            .map_err(|_| anyhow!("Invalid signature length"))?
    );

    // メッセージを構築
    let message = format!("{}{}", timestamp, body);

    // 署名検証
    match verifying_key.verify(message.as_bytes(), &signature) {
        Ok(()) => Ok(true),
        Err(_) => Ok(false),
    }
}