<?php

class StoreFileDownloadApi {
	protected $viewPath;

	public function __construct() {
		$this->viewPath = dirname(__FILE__).'/view';
	}

	/**
	 * @param StoreNavigation $request
	 * @return no-return
	 */
	public function process(StoreNavigation $request) {
		$invoiceHash = $request->getArg(1);
		$fileName = $request->getArg(2);

		$order = StoreModuleOrder::findByHash($invoiceHash);
		$valid = $order && $order->getInvoiceDocumentNumber();
		if( $valid ) {
			$valid = false;
			foreach( $order->getItems() as $item ) {
				if( $item instanceof StoreModuleOrderItem && count($item->files) ) {
					$valid = true;
					break;
				}
			}
		}

		if( !$valid ) {
			@header("Connection: close", true, 404);
			exit;
		}

		if (!($order->getState() === StoreModuleOrder::STATE_COMPLETE || $order->getState() === StoreModuleOrder::STATE_PAID)) {
			echo "Can't download file yet - order is incomplete (waiting for payment confirmation). Please try again later.";
			@header("Connection: close", true, 403);
			exit();
		}

		if ($fileName) {
			foreach( $order->getItems() as $item ) {
				foreach ($item->files as $file) {
					if ($file->name === $fileName) {
						$filePath = $file->getOrderedFile();
						if (file_exists($filePath)) {
							header($_SERVER["SERVER_PROTOCOL"] . " 200 OK");
							header("Cache-Control: public"); // needed for internet explorer
							header("Content-Transfer-Encoding: Binary");
							header("Content-Length:".filesize($filePath));
							header("Content-Disposition: attachment; filename=" . basename($file->src));
							if (function_exists('mime_content_type')) {
								header("Content-Type: " . mime_content_type($filePath));
							} elseif (function_exists('finfo_open') && function_exists('finfo_file') && defined('FILEINFO_MIME_TYPE')) {
								$finfo = finfo_open(FILEINFO_MIME_TYPE);
								header("Content-Type: " . finfo_file($finfo, $filePath));
							} else {
								header("Content-Type: application/octet-stream");
							}
							readfile($filePath);
							die();
						}
					}
				}
			}
			@header("Connection: close", true, 404);
			exit();
		}

		if( $order->getLang() ) {
			$request->lang = $order->getLang();
			SiteModule::setLang($request->lang);
		}

		$invoiceLogo = StoreData::getInvoiceLogo();
		$logoImageAlign = $invoiceLogo ? StoreData::getLogoAlign() : '';

		$this->renderView($this->viewPath.'/file-download.php', array(
			"order" => $order,
			"invoiceTitlePhrase" => StoreData::getInvoiceTitlePhrase(),
			"invoiceTextBeginning" => StoreData::getInvoiceTextBeginning(),
			"invoiceTextEnding" => StoreData::getInvoiceTextEnding(),
			"sellerCompanyInfo" => StoreData::getCompanyInfo(),
			"logoImage" => $invoiceLogo ? getBaseUrl() . $invoiceLogo : null,
			"logoImageAlign" => $logoImageAlign,
			"formattedDate" => StoreData::getFormattedDate(),
			"fileDownloadUrl" => StorePaymentApi::getFileDownloadUrl($request, $order),
		));
		if (function_exists('ini_set')) @ini_set("display_errors", false);

		exit();
	}

	/**
	 * Render template.
	 * @param string $templatePath path to template file.
	 * @param array $vars associative array with template variable values.
	 */
	protected function renderView($templatePath, $vars) {
		extract($vars);
		require $templatePath;
	}
}
