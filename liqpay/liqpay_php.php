<?php
/**
 * liqpay_php.php — LiqPay helper для PHP
 * Підключається через require_once
 */
class LiqPayPHP {
    private $public_key;
    private $private_key;
    const CHECKOUT_URL = 'https://www.liqpay.ua/api/3/checkout';

    public function __construct($public_key, $private_key) {
        $this->public_key  = trim($public_key);
        $this->private_key = trim($private_key);
    }

    public function encode($params) {
        return base64_encode(json_encode($params, JSON_UNESCAPED_UNICODE));
    }

    public function signature($data) {
        return base64_encode(sha1($this->private_key . $data . $this->private_key, true));
    }

    public function createPaymentUrl($order_id, $amount, $description, $server_url, $result_url, $currency = 'UAH') {
        $params = [
            'action'      => 'pay',
            'version'     => 3,
            'public_key'  => $this->public_key,
            'amount'      => $amount,
            'currency'    => $currency,
            'description' => $description,
            'order_id'    => $order_id,
            'language'    => 'uk',
            'server_url'  => $server_url,
            'result_url'  => $result_url,
        ];
        $data = $this->encode($params);
        $sig  = $this->signature($data);
        return self::CHECKOUT_URL . '?data=' . urlencode($data) . '&signature=' . urlencode($sig);
    }
}
