<?php

class FormInquiriesApi
{
	protected function getBuilderRequestData(FormNavigation $request, $actionId, $signatureFields = array())
	{
		header('Access-Control-Allow-Origin: *', true); // allow cross domain requests

		$data = $request->getBodyAsJson();
		if (!$data || !is_object($data) || !isset($data->sig)) {
			FormModule::respondWithJson(array(
				"error" => array("code" => 1, "message" => "Bad request")
			));
		}

		$sigCheckStr = FormModule::$siteInfo->websiteUID . "|" . $actionId;
		foreach ($signatureFields as $k)
			$sigCheckStr .= "|" . $k . "=" . $data->{$k};

		$expectedHash = md5($sigCheckStr);
		$hash = $this->publicDecrypt($data->sig);
		if ($hash !== $expectedHash) {
			FormModule::respondWithJson(array(
				"error" => array("code" => 2, "message" => "Bad signature")
			));
		}

		return $data;
	}

	/**
	 * @param FormNavigation $request
	 * @param bool $homePage
	 * @return array{hr_out: string|null, requestHandled: bool}
	 */
	public static function process(FormNavigation $request, $homePage = false) {
		$actionHandled = false;
		if ($homePage) {
			$ctrl = new self();
			$key = $request->getArg(0) ?: '';
			$action = array_map('ucfirst', explode('-', strtolower(preg_replace('#[^a-zA-Z0-9\-]+#', '', $key))));
			$action[0] = strtolower($action[0]);
			$method = implode('', $action).'Action';
			if (method_exists($ctrl, $method)) {
				$actionHandled = true;
				call_user_func(array($ctrl, $method), $request);
			}
		}
		return array(null, $actionHandled);
	}

	protected function formsUuidsAction(FormNavigation $request)
	{
		$data = $this->getBuilderRequestData($request, 'forms-uuids');

		$result = [];
		$list = FormModuleInquiries::findAll();
		foreach ($list as $idx => $li) {
			$result[$li->getFormId()] = $li->getFormId();
		}

		FormModule::respondWithJson(array("ok" => true, "list" => array_keys($result)));
	}

	protected function formsLogAction(FormNavigation $request)
	{
		$data = $this->getBuilderRequestData($request, 'forms-log');

		if (isset($data->formUuid) && $data->formUuid != 'all') {
			$formId = $data->formUuid;
			$list = FormModuleInquiries::findByFormId($formId);
		} else {
			$list = FormModuleInquiries::findAll();
		}

		foreach ($list as $idx => $li) {
			$list[$idx] = $li->jsonSerialize();
		}

		FormModule::respondWithJson(array("ok" => true, "list" => $list));
	}

	protected function removeInquiryAction(FormNavigation $request)
	{
		$data = $this->getBuilderRequestData($request, 'remove-inquiry', array("id"));

		$inquiry = FormModuleInquiries::findById($data->id);
		if ($inquiry) {
			$inquiry->delete();
		}

		FormModule::respondWithJson(array("ok" => true));
	}

	protected function removeAllInquiryAction(FormNavigation $request)
	{
		$data = $this->getBuilderRequestData($request, 'remove-all-inquiry', array('formUuid'));

		$deleteCount = FormModuleInquiries::deleteByFilter([
			FormModuleInquiries::FILTER_FORM_ID => $data->formUuid,
		]);

		FormModule::respondWithJson(array("ok" => $deleteCount !== null, "count" => $deleteCount));
	}

	private function publicDecrypt($encData)
	{
		require_once __DIR__ . '/../../phpseclib/Crypt/Random.php';
		require_once __DIR__ . '/../../phpseclib/Math/BigInteger.php';
		require_once __DIR__ . '/../../phpseclib/Crypt/Hash.php';
		require_once __DIR__ . '/../../phpseclib/Crypt/RSA.php';
		$rsa = new \phpseclib\Crypt\RSA();
		$rsa->loadKey($this->getSecurityPublicKey());
		$rsa->setEncryptionMode(\phpseclib\Crypt\RSA::ENCRYPTION_PKCS1);
		$data = @$rsa->decrypt(base64_decode($encData));
		return ($data === false) ? null : $data;
	}

	private function publicEncrypt($data)
	{
		require_once __DIR__ . '/../../phpseclib/Crypt/Random.php';
		require_once __DIR__ . '/../../phpseclib/Math/BigInteger.php';
		require_once __DIR__ . '/../../phpseclib/Crypt/Hash.php';
		require_once __DIR__ . '/../../phpseclib/Crypt/RSA.php';
		$rsa = new \phpseclib\Crypt\RSA();
		$rsa->loadKey($this->getSecurityPublicKey());
		$rsa->setEncryptionMode(\phpseclib\Crypt\RSA::ENCRYPTION_PKCS1);
		$encData = @$rsa->encrypt($data);
		return ($encData === false) ? null : base64_encode($encData);
	}

	private function getSecurityPublicKey()
	{
		return "-----BEGIN PUBLIC KEY-----\n"
			. "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzeio9jpU3e31Rlc4w0SA\n"
			. "jOWOkjS++yZnyaziUDyLXupLxELER2SHyA2nFG7eOuKPohYFomX/GQdtbMLLL+4J\n"
			. "/IofyOi1t/jlafY3wzTYCN2u8pfYP6L5sChuE3zb+g7Gvq/1XewiroDChy0mE+zr\n"
			. "mATJp+UY2zcc60S0aiv+mFaGHrD6vyK/uUlfd2XbLNjWJnOe4HKq/uZb9MK8yY34\n"
			. "snpLzrwmnxjS0/UDvljdrUAA1gIYA8rIO08AiyT9evTQEMyp4861COfGVdASHi/i\n"
			. "O5piPRMp1BuY0LYk0ykA79gI7kygk5qQRcHJLZ1jhsm4jHl7chrjJ3jis8Pk4ico\n"
			. "KwIDAQAB\n"
			. "-----END PUBLIC KEY-----\n";
	}

}
