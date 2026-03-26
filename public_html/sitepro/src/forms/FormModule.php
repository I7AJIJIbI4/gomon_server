<?php

/**
 * Description of FormModule
 */
class FormModule
{

	/** @var FormNavigation */
	public static $formNav;
	/** @var stdClass */
	public static $initData;
	/** @var SiteInfo */
	public static $siteInfo;
	/** @var string */
	public static $storeAnchor;

	/**
	 * Translate store module variable.
	 * @param string $key
	 * @return string
	 */
	public static function __($key)
	{
		$langKey = (self::$formNav && self::$formNav->lang) ? self::$formNav->lang : '-';
		return SiteModule::__($key, $langKey);
	}

	public static function init($data, SiteInfo $siteInfo)
	{
		@setlocale(LC_CTYPE, 'C.UTF-8');
		self::$initData = $data;
		self::$siteInfo = $siteInfo;
	}

	/**
	 * Get orders log file
	 * @return string
	 */
	public static function getLogFile()
	{
		return dirname(__FILE__) . '/forms.log';
	}

	/**
	 * Get orders log file in jsonl format
	 * @return string
	 */
	public static function getLogFileJsonl()
	{
		return dirname(__FILE__) . '/forms.jsonl.log';
	}

	/**
	 * Parse request to perform special actions
	 * @param SiteRequestInfo $requestInfo
	 * @return array{hr_out: string|null, requestHandled: bool}
	 */
	public static function parseRequest($requestInfo)
	{
		$request = self::handleFormNav($requestInfo);

		try {
			$out = FormInquiriesApi::process($request, (!$requestInfo->page || $requestInfo->page['id'] == self::$siteInfo->homePageId));
		} catch (Exception $ex) {
			self::exitWithError($ex->getMessage());
		}

		return $out;
	}

	/**
	 * Build store request object.
	 * @param SiteRequestInfo $reqInf
	 * @param array $thisPage page definition as key value pair array
	 * @return FormNavigation
	 */
	private static function handleFormNav($reqInf)
	{
		self::$formNav = new FormNavigation();
		self::$formNav->args = $reqInf->urlArgs;
		self::$formNav->lang = $reqInf->lang;
		self::$formNav->defLang = self::$siteInfo->defLang;
		self::$formNav->baseLang = self::$siteInfo->baseLang;
		self::$formNav->basePath = self::$siteInfo->baseDir;
		self::$formNav->baseUrl = preg_replace('#^[^\:]+\:\/\/[^\/]+(?:\/|$)#', '/', self::$siteInfo->baseUrl)
			. ((!self::$siteInfo->modRewrite && !preg_match('#\?route=#', self::$siteInfo->baseUrl)) ? '?route=' : '');

		return self::$formNav;
	}

	/**
	 * Log sent form as store order
	 * @param string $pageId id oage
	 * @param string $formId id form
	 * @param array $formDef form definition (associative array)
	 * @param array $formData form data (input by user)
	 */
	public static function logForm($attachmentsLogDir, $pageId, $formId, $formDef, $formData)
	{
		$fields = array();

		$movedFiles = array();
		if ($formDef) {
			foreach ($formDef as $idx => $item) {
				if ($item["type"] === "file") {
					$fieldName = "wb_input_$idx";
					if( !isset($_FILES[$fieldName]) )
						continue;
					if (!isset($item["settings"]["fileSaving"]) || !$item["settings"]["fileSaving"]) {
						continue;
					}
					if( !file_exists($attachmentsLogDir) ) {
						if( !mkdir($attachmentsLogDir, 0755) ) {
							error_log('[Form error]: Failed to create a directory for attachments');
							continue;
						}
					}
					if( !file_exists($attachmentsLogDir . DIRECTORY_SEPARATOR . $formId) ) {
						if( !mkdir($attachmentsLogDir . DIRECTORY_SEPARATOR . $formId, 0755) ) {
							error_log('[Form error]: Failed to create a directory for attachments');
							continue;
						}
					}
					if( !is_dir($attachmentsLogDir) || !is_dir($attachmentsLogDir . DIRECTORY_SEPARATOR . $formId) ) {
						error_log('[Form error]: Attachments inode on the server is not a directory');
						continue;
					}
					$value = array();
					foreach( $_FILES[$fieldName]["tmp_name"] as $fileIdx => $fileTmpName) {
						if( !$fileTmpName )
							continue;
						$fileName = $_FILES[$fieldName]["name"][$fileIdx];

						$secureFileName = $fileName;
						$secureFileName = preg_replace("#[\\\\/<>\\?;:,=]+#isu", "_", $secureFileName);
						$secureFileName = preg_replace("#\\.\\.+#isu", ".", $secureFileName);

						$tmpCopyName = $attachmentsLogDir . DIRECTORY_SEPARATOR . $formId . DIRECTORY_SEPARATOR . $secureFileName;
						if( !copy($fileTmpName, $tmpCopyName) ) {
							foreach( $movedFiles as $tmpCopyName )
								unlink($tmpCopyName);
							error_log('[Form error]: Failed to move uploaded file to attachments directory');
							continue;
						}
						$movedFiles[] = $tmpCopyName;

						$value[] = '/' . $formId . '/' . $secureFileName;
					}

					$fields[] = FormModuleInquiriesField::fromJson(array_merge($item, array('answer' => count($value) <= 1 ? reset($value) : $value)));
				} else {
					$value = isset($formData[$idx]) ? $formData[$idx] : null;
					$fields[] = FormModuleInquiriesField::fromJson(array_merge($item, array('answer' => $value)));
				}
			}
		}
		FormModuleInquiries::create($pageId, $formId)
			->setFields($fields)
			->setDateTime(date('Y-m-d H:i:s'))
			->save();
	}

	private static function exitWithError($error)
	{
		echo $error;
		exit();
	}

	/**
	 * Respond with JSON.
	 * @param mixed $data data to respond with.
	 */
	public static function respondWithJson($data)
	{
		if (session_id()) session_write_close();
		header('Content-Type: application/json; charset=utf-8', true);
		echo json_encode($data);
		exit();
	}
}
