<?php

class GatewayPaypalV1 extends PaymentGateway
{

	const WEB_URL = 'https://www.paypal.com/cgi-bin/webscr';
	const TEST_WEB_URL = 'https://www.sandbox.paypal.com/cgi-bin/webscr';

	private $isTest;

	public function init()
	{
		$this->isTest = (isset($this->config->demo) && $this->config->demo);
	}

	public static $supportedLocales = array(
		'en_US', 'en_AU', 'en_GB', 'fr_CA', 'es_ES',
		'it_IT', 'fr_FR', 'de_DE', 'pt_BR', 'zh_CN',
		'da_DK', 'zh_HK', 'he_IL', 'no_NO', 'pl_PL',
		'pt_PT', 'ru_RU', 'sv_SE', 'th_TH', 'zh_TW',
		'nl_NL'
	);

	public static function filterLocale($locale)
	{
		foreach (self::$supportedLocales as $loc) {
			if ($loc == $locale) {
				if ($locale == 'nl_NL') return 'nl_NL/NL';
				return $locale;
			}
		}
		return 'en_US';
	}

	public function getTransactionId()
	{
		return $this->getQueryParam('txnId', $this->getFormParam('custom'));
	}

	private function getClientName()
	{
		return $this->getFormParam('address_name');
	}

	private function getClientEmail()
	{
		return $this->getFormParam('payer_email');
	}

	private function getClientAddress()
	{
		$address = array();
		if (($v = $this->getFormParam('address_street'))) $address[] = $v;
		if (($v = $this->getFormParam('address_city'))) $address[] = $v;
		if (($v = $this->getFormParam('address_country'))) $address[] = $v;
		return implode(', ', $address);
	}

	public function getClientInfo()
	{
		$info = array();
		if (($v = $this->getClientName())) $info['name'] = $v;
		if (($v = $this->getClientEmail())) $info['email'] = $v;
		if (($v = $this->getClientAddress())) $info['address'] = $v;
		return $info;
	}

	public function createFormFields($formVars)
	{
		if (isset($formVars['notify_url'])) {
			$formVars['notify_url'] .= '?txnId=' . $formVars['custom'];
		}
		return array(
			'<input type="hidden" name="notify_url" value="' . $formVars['notify_url'] . '" />'
		);
	}

	public function callback(StoreModuleOrder $order = null)
	{
		$webUrl = $this->isTest ? self::TEST_WEB_URL : self::WEB_URL;
		$req_ = array('cmd' => '_notify-validate');
		$reqRaw = array_merge($req_, $_POST);
		$resp = $this->httpRequest($webUrl, $reqRaw);
		if ($resp['body'] != 'VERIFIED') {
			error_log("Paypal IPN verify response:\n" . print_r($resp, true));
		}
		if ($order) {
			$status = $this->getFormParam('payment_status');
			if ($status == 'Refunded') {
				$order->setState(StoreModuleOrder::STATE_REFUNDED);
				$order->save();
			} else if ($status == 'Failed') {
				$order->setState(StoreModuleOrder::STATE_FAILED);
				$order->save();
			} else if ($status == 'Completed') {
				return true;
			}
		}
		return false;
	}

	private function urlParamsToString($params)
	{
		if (!is_array($params)) {
			return $params;
		}
		$prm = '';
		foreach ($params as $k => $v) {
			if (!$k || is_null($v) || $v === false) {
				continue;
			}
			$uv = urlencode($v);
			$prm .= ($prm ? '&' : '') . urlencode($k) . (($uv || $uv === '0') ? ('=' . $uv) : '');
		}
		$prmstr = str_replace('%2F', '/', $prm);
		return $prmstr ? $prmstr : false;
	}

	private function httpRequest($url, $post_vars = null)
	{
		$post_contents = '';
		if ($post_vars) {
			if (is_array($post_vars)) {
				$post_contents = $this->urlParamsToString($post_vars);
			} else {
				$post_contents = $post_vars;
			}
		}

		$uinf = parse_url($url);
		$host = $uinf['host'];
		$path = isset($uinf['path']) ? $uinf['path'] : '';
		$path .= (isset($uinf['query']) && $uinf['query']) ? '?' . $uinf['query'] : '';
		$headers = array(
			($post_contents ? 'POST' : 'GET') . " $path HTTP/1.1",
			"Host: $host",
		);
		if ($post_contents) {
			$headers[] = "Content-Type: application/x-www-form-urlencoded";
			$headers[] = "Content-Length: " . strlen($post_contents);
		}

		$ch = curl_init();
		curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);
		curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, 0);
		curl_setopt($ch, CURLOPT_URL, $url);
		curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
		curl_setopt($ch, CURLOPT_HEADER, 1);
		curl_setopt($ch, CURLOPT_TIMEOUT, 600);
		curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

		if ($post_contents) {
			curl_setopt($ch, CURLOPT_POST, 1);
			curl_setopt($ch, CURLOPT_POSTFIELDS, $post_contents);
		}

		$data = curl_exec($ch);
		$header_size = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
		$result['url'] = $url . ' (IP: ' . (($v = gethostbyname($host)) == $host ? 'UNKNOWN' : $v) . ')';
		$result['curl_err'] = curl_error($ch);
		$result['curl_ern'] = curl_errno($ch);
		$result['post'] = $post_contents;
		$result['shd'] = $headers;
		$result['header'] = substr($data, 0, $header_size);
		$result['body'] = substr($data, $header_size);
		$result['http_code'] = curl_getinfo($ch, CURLINFO_HTTP_CODE);
		$result['last_url'] = curl_getinfo($ch, CURLINFO_EFFECTIVE_URL);
		$result['error'] = array('code' => curl_errno($ch), 'message' => curl_error($ch));

		curl_close($ch);
		return $result;
	}

}
